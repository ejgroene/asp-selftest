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


Handler = enum.IntEnum('Handler', ['LOGGER', 'INIT', 'LOAD', 'GROUND', 'SOLVE'], start=0)


class Main:
    def __init__(self, clingo_session):
        self.clingo_session = clingo_session

    """ Main Application dictated by Clingo, to be fed to clingo_main() """
    program_name = "clingo+"
    message_limit = 20

    def main(self, control, files):
        self.clingo_session(control=control, files=files, logger=self.logger,
                            message_limit=self.message_limit, main=self)

    #@guard
    def logger(self, code, message):
        self._logger(code, message)

        
    def set_logger(self, logger_chain):
        self._logger = logger_chain


def session2(plugins=(), **etc):
    assert len(plugins) > 0, plugins
    def next_plugin_func(i):
        def next_plugin(**etc):
            assert i < len(plugins), f"No more plugins {plugins}[{i}]"
            return plugins[i](next_plugin_func(i+1), **etc)
        return next_plugin
    return next_plugin_func(0)(**etc)()


@test
def test_session2():
    def hello_plugin(next, name=None):
        def hello():
            return f"Hello {name}"
        return hello
    test.eq("Hello John", session2(plugins=(hello_plugin,), name="John"))


@test
def test_session2_sequencing():
    trace = []
    def hello_goodbye_plugin(next, name=None):
        def hi():
            trace.append(f"Hi {name}!")
        def jo():
            trace.append(f"Jo {name}!")
        return hi, jo
    def sequencer_plugin(next, **etc):
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

    def error_handling_plugin(next, **etc):

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

    def clingo_main_plugin(next, arguments=(), **etc):
                
        class App:
                    
            def main(self, control, files):
                self._logger, main = next(control=control, files=files, **etc)
                self.result = main()
                        
            def logger(self, code, message):
                self._logger(code, message)
                        
        def main():
            app = App()
            err = clingo.clingo_main(app, arguments)
            if isinstance(app.result, Exception):
                assert err in (ExitCode.UNKNOWN, ExitCode.ERROR), f"ExitCode {err!r}"
                raise app.result
            return app.result
                
        return main

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

    plugins = (clingo_main_plugin, source_plugin, error_handling_plugin, clingo_sequencer_plugin, clingo_defaults_plugin)
    file1 = tmp_path/'file1.lp'
    file1.write_text('a.')
    result = session2(plugins=plugins, arguments=(file1.as_posix(),))
    test.eq(True, result.satisfiable)
    with test.raises(SyntaxError) as e:
        session2(plugins=plugins, source="error", label='yellow')
    test.endswith(str(e.exception), f"-yellow.lp:2:1-2: error: syntax error, unexpected EOF\n")


def clingo_session_base(main=None, logger=None, plugins=(), source=None, files=(), **kwargs):

    assert plugins, "No plugins."

    def redirect_logger(code, message):
        caller(0, Handler.LOGGER)(code, message)

    if main:
        main.set_logger(redirect_logger)
    if not logger:
        logger = redirect_logger

    handlerssets = [plugin(plugins=plugins, logger=logger, **kwargs) for plugin in plugins]

    def caller(i, h):
        if i >= len(plugins):
            return lambda *a: None
        handler = handlerssets[i][h]
        @functools.wraps(handler)
        def call(*args):
            #print(f"call: {handler.__qualname__}({', '.join(map(str,args))})", file=sys.stderr)
            return handler(caller(i+1, h), *args)
        return call

    control = caller(0, Handler.INIT)()
    caller(0, Handler.LOAD)(control, source, files)
    caller(0, Handler.GROUND)(control)
    return control, caller(0, Handler.SOLVE)(control)
        

def test_plugin(**etc):
    def logger(next, code, message):
        pass
    def init(next):
        pass
    def load(next, control):
        pass
    def ground(next, control):
        pass
    def solve(next, control):
        pass
    return logger, init, load, ground, solve


@test
def have_my_own_handler_doing_nothing():
    log = []
    def my_own_handler(logger=None, plugins=(), **etc):
        log.append(etc)
        def logme(*args):
            log.append((*plugins, *args))
            return len(log)
        return logme, logme, logme, logme, logme
    control, result = clingo_session_base(plugins=[my_own_handler], more='here')
    test.eq({'more': 'here'}, log[0])
    test.eq(5, result)
    test.eq([
        (my_own_handler, test.any,),
        (my_own_handler, test.any, 2, None, ()),
        (my_own_handler, test.any, 2),
        (my_own_handler, test.any, 2),
    ], log[1:], diff=test.diff)

        