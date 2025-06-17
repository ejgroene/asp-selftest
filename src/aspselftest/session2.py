"""

    EXPERIMENT with easier way to use plugins.

    It tries to separate the Clingo-specific sequencing:
        Control() -> Load -> Ground -> Solve

    from the plugin logic. Or: make the sequencing a plugin.

"""

import pathlib
import subprocess
import os
import sys
import functools
import enum
import tempfile

import clingo.ast
import selftest

test = selftest.get_tester(__name__)


def session2(plugins=(), **etc):
    """ Calls each plugin (factory) with the next one as first argument, followed by **etc.
        The first plugin must return a callable wich is called immediately. """
    assert len(plugins) > 0, plugins
    def next_plugin_func(i):
        def next_plugin(**etc):
            assert i < len(plugins), f"No more plugins after '{plugins[-1].__name__}'"
            return plugins[i](next_plugin_func(i+1), **etc)
        return next_plugin
    return next_plugin_func(0)(**etc)()


@test
def test_session2():
    def hello_plugin(next, name=None):
        """ A plugin is called with the next plugin as first argument, followed by all the given keyword args.
            The first plugin must return a callable. """
        with test.raises(AssertionError, "No more plugins after 'hello_plugin'"):
            next()
        def hello():
            return f"Hello {name}"
        return hello
    test.eq("Hello John", session2(plugins=(hello_plugin,), name="John"))


@test
def test_session2_sequencing():
    trace = []
    def hello_goodbye_plugin(next, name=None):
        """ This plugin only works with the sequencer, which expects two functions."""
        def hi():
            trace.append(f"Hi {name}!")
        def jo():
            trace.append(f"Jo {name}!")
        return hi, jo
    def sequencer_plugin(next, **etc):
        """ This plugin expects two functions and returns one (as required)."""
        hello, goodbye = next(**etc)
        def main():
            hello()
            goodbye()
        return main
    test.eq(None, session2(plugins=(sequencer_plugin, hello_goodbye_plugin,), name="John"))
    test.eq(['Hi John!', 'Jo John!'], trace)


# ExitCode, see clasp_app.h
class ExitCode(enum.IntEnum):
    UNKNOWN   =   0  #/*!< Satisfiability of problem not known; search not started.   */
    INTERRUPT =   1  #/*!< Run was interrupted.                                       */
    SAT       =  10  #/*!< At least one model was found.                              */
    EXHAUST   =  20  #/*!< Search-space was completely examined.                      */
    MEMORY    =  33  #/*!< Run was interrupted by out of memory exception.            */
    ERROR     =  65  #/*!< Run was interrupted by internal error.                     */
    NO_RUN    = 128  #/*!< Search not started because of syntax or command line error.*/

@test
def test_session2_clingo_sequencing(tmp_path):

    def clingo_defaults_plugin(next, control=None, files=(), **etc):
        
        def logger(code, message):
            print("LOG:", code, message)
                    
        def load():
            for filename in files:
                control.load(filename)
                        
        return logger, load, control.ground, control.solve

    def clingo_sequencer_plugin(next, **etc):
        
        logger, load, ground, solve = next(**etc)
                
        def main():
            load()
            ground()
            return solve()
                
        return logger, main

    def source_plugin(next, source=None, label='string', files=(), **etc):
        
        keep_file = None
                
        if source:
            keep_file = tempfile.NamedTemporaryFile('w', suffix=f"-{label}.lp") 
            keep_file.write(source)
            keep_file.flush()
            files=(keep_file.name, *files)
                    
        def main():
            keep_file
            return _main()
                
        logger, _main = next(files=files, **etc)
        return logger, main

    def clingo_main_plugin(next, arguments=(), **etc):
        """ Uses clingo_main() to drive the plugins. """
                
        class App:
            """ As per Clingo spec: callbacks main() and logger(). """
                    
            def main(self, control, files):
                self._logger, _main = next(control=control, files=files, **etc)  # [3]
                self.result = _main()
                        
            def logger(self, code, message):
                self._logger(code, message)
                        
        def main():
            app = App()
            app.exitcode = clingo.clingo_main(app, arguments)  # [2]
            # do not know what to do with exitcode yet
            #assert err in (ExitCode.UNKNOWN, ExitCode.ERROR), f"ExitCode {err!r}"
            return app.result
                
        return main  #[1]

    class error_handling_plugin:
        
        def after(next, **etc):

            _exception = None
            _logger, _main = next(**etc)
            
            def logger(code, message):
                nonlocal _exception
                _exception = SyntaxError(message)
                        
            def main():
                try:
                    return _main()
                except RuntimeError as e:
                    assert str(e) in ['parsing failed']
                    return _exception if _exception else e
                        
            return logger, main

        def before(next, **etc):
            
            _main = next(**etc)
                    
            def main():
                result = _main()
                if isinstance(result, Exception):     # [4]
                    raise result
                return result
                    
            return main
        


    plugins = (
        error_handling_plugin.before,  # raises errors if any
        clingo_main_plugin,
        error_handling_plugin.after,   # catches all errors
        source_plugin,
        clingo_sequencer_plugin,
        clingo_defaults_plugin)
    file1 = tmp_path/'file1.lp'
    file1.write_text('a.')
    result = session2(plugins=plugins, arguments=(file1.as_posix(),))
    test.eq(True, result.satisfiable)
    with test.raises(SyntaxError) as e:
        session2(plugins=plugins, source="error", label='yellow')
    test.endswith(str(e.exception), f"-yellow.lp:2:1-2: error: syntax error, unexpected EOF\n")
