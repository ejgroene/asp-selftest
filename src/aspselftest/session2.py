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
import tempfile

import selftest

from .plugins.clingoexitcodes import ExitCode

from .plugins import (
    clingo_main_plugin,
    source_plugin,
    clingo_control_plugin,
    clingo_syntaxerror_plugin,
    clingo_sequencer_plugin,
)


from .plugins._testplugins import (
    clingo_defaults_plugin,
)

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

   
common_plugins = (
    clingo_syntaxerror_plugin,
    clingo_sequencer_plugin,
    clingo_defaults_plugin,
)

def clingo_main_session(**kwargs):
    return session2(
        plugins=(
            clingo_main_plugin,
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
def clingo_main_session_happy_flow(tmp_path):
    file1 = tmp_path/'file1.lp'
    file1.write_text('a.')
    exitcode = clingo_main_session(arguments=(file1.as_posix(),))
    test.eq(exitcode, ExitCode.SAT)

@test
def clingo_main_session_error(tmp_path):
    file1 = tmp_path/'error.lp'
    file1.write_text('error')
    with test.raises(SyntaxError):
        clingo_main_session(arguments=(file1.as_posix(),))

@test
def session_with_source():
    with test.raises(SyntaxError) as e:
        clingo_session(source="error", label='yellow')
    test.endswith(str(e.exception), f"-yellow.lp:2:1-2: error: syntax error, unexpected EOF\n")


@test
def test_session2_not_wat():
    solve_handle = clingo_session(source="a. b. c(a).", yield_=True)
    with solve_handle as result:
        for model in result:
            test.eq('a b c(a)', str(model))


@test
def session_with_file(tmp_path):
    file1 = tmp_path/'test.lp'
    file1.write_text('test(1).')
    solveresult = clingo_session(files=(file1.as_posix(),))
    test.truth(solveresult.satisfiable)