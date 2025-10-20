"""

    EXPERIMENT with easier way to use plugins.

    It tries to separate the Clingo-specific sequencing:
        Control() -> Load -> Ground -> Solve

    from the plugin logic. Or: make the sequencing a plugin.

"""

import selftest
test = selftest.get_tester(__name__)

from .plugins.misc import write_file, ExitCode

from .plugins import (
    clingo_main_plugin,
    source_plugin,
    clingo_control_plugin,
    clingo_syntaxerror_plugin,
    clingo_sequencer_plugin,
    clingo_defaults_plugin,
    testrunner_plugin,
    clingo_reify_plugin,
    stdin_to_tempfile_plugin,
)

import clingo
VERSION = '.'.join(map(str,clingo.version()))


def session2(plugins=(), **etc):
    """ Calls each plugin (factory) with the next one as first argument, followed by **etc.
        The first plugin must return a callable wich is called immediately. """
    assert len(plugins) > 0, plugins
    def get_plugin_func(i):
        def get_plugin(**etc):
            assert i < len(plugins), f"No more plugins after '{plugins[-1].__name__}'"
            return plugins[i](get_plugin_func(i+1), **etc)
        return get_plugin
    return get_plugin_func(0)(**etc)()


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

   
common_plugins = (
    clingo_syntaxerror_plugin,
    clingo_sequencer_plugin,
    testrunner_plugin,
    clingo_reify_plugin,
    clingo_defaults_plugin,
)

def clingo_main_session(**kwargs):
    return session2(
        plugins=(
            clingo_main_plugin,
            stdin_to_tempfile_plugin,
            *common_plugins),
        **kwargs)

def clingo_session(**kwargs):
    return session2(
        plugins=(
            source_plugin,
            clingo_control_plugin,
            *common_plugins),
        **kwargs)


@test
def clingo_main_session_happy_flow(stdout, tmp_path):
    file1 = tmp_path/'file1.lp'
    file1.write_text('a.')
    exitcode = clingo_main_session(arguments=(file1.as_posix(),))
    test.eq(exitcode, ExitCode.SAT)
    out = stdout.getvalue()
    test.startswith(out, f"clingo+ version {VERSION}\nReading from ")
    i = out.find("Time: 0.0")
    j = out.find("s)\na\n")
    out = out[:i] + 'xxx' + out[j:] 
    test.contains(out, "Answer: 1 (xxxs)\na\nSATISFIABLE\n\nModels       : 1+\n")


@test
def clingo_main_session_error(tmp_path, stdout, stderr):
    file1 = write_file(tmp_path/'error.lp', 'error')
    with test.raises(SyntaxError, "syntax error, unexpected EOF") as e:
        clingo_main_session(arguments=(file1,))
    err = stderr.getvalue()
    out = stdout.getvalue()
    test.eq('', err)
    test.startswith(out, f"clingo+ version {VERSION}\nReading from ")
    test.contains(out, f"{file1[-38:]}\nUNKNOWN\n\nModels       : 0+\nCalls        : 1\nTime")
    test.endswith(e.exception.text, "    1 error\n      ^ syntax error, unexpected EOF")


@test
def session_with_source(stderr):
    with test.raises(SyntaxError) as e:
        clingo_session(source="error", label='yellow')
    msg = str(e.exception)
    test.startswith(msg, "syntax error, unexpected EOF (tmp")
    test.endswith(msg, f"-yellow.lp, line 2)")


@test
def test_session2_not_wat(stdout):
    solve_handle = clingo_session(source="a. b. c(a).", yield_=True)
    with solve_handle as result:
        for model in result:
            test.eq('a b c(a)', str(model))
    test.endswith(stdout.getvalue(), "-string.lp\nTesting base\n  base\n")


@test
def session_with_file(tmp_path, stdout):
    file1 = tmp_path/'test.lp'
    file1.write_text('test(1).')
    solveresult = clingo_session(files=(file1.as_posix(),))
    test.truth(solveresult.satisfiable)
    test.endswith(stdout.getvalue(), "test.lp\nTesting base\n  base\n")
