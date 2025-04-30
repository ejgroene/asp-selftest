
"""
    Top Level Code + Integration Tests
"""

import pathlib
import subprocess
import os
import clingo

import selftest
test =  selftest.get_tester(__name__)

from .session import clingo_session_base, Main
from .plugins import defaultcontrol_plugin, sourcesupport_plugin, syntaxerror_plugin, testrunner_plugin, clingodefault_plugin




default_plugins = (
    sourcesupport_plugin,
    defaultcontrol_plugin,
    syntaxerror_plugin,
    testrunner_plugin,
    clingodefault_plugin
)
   

def clingo_session(**etc):
    return clingo_session_base(plugins=default_plugins, **etc)


# entry point
def clingo_plus_main_ng():
    clingo.application.clingo_main(Main(clingo_session), arguments=())


def run_clingo_plus_main(code):
    path = pathlib.Path(__file__).parent
    return subprocess.run(
        ["python", "-c", f"from aspselftest.__main__ import clingo_plus_main_ng; clingo_plus_main_ng()"],
        env=os.environ | {'PYTHONPATH': path},
        input=code,
        capture_output=False)


@test
def test_simple():
    control, result = clingo_session(source="a.")
    test.truth(result.satisfiable)


@test
def simple_load_error():
    with test.raises(SyntaxError) as e:
        clingo_session(source='a', label='src_a')
    msg = str(e.exception)
    test.startswith(msg, "syntax error, unexpected EOF (")
    test.endswith(msg, "src_a.lp, line 2)")
    msg, args = e.exception.args
    test.eq('syntax error, unexpected EOF', msg)
    test.contains(args[0], '-src_a.lp')
    test.eq(2, args[1]),
    test.eq(None, args[2])
    test.eq('    1 a\n      ^ syntax error, unexpected EOF', args[3])


@test
def simple_ground_error():
    with test.raises(SyntaxError) as e:
        clingo_session(source='a :- b.', label='src_b')
    tmpfilename = e.exception.args[1][0]
    test.startswith(str(e.exception), "atom does not occur in any rule head:  b (")
    test.endswith(str(e.exception), "-src_b.lp, line 1)")
    test.eq(('atom does not occur in any rule head:  b',
             (tmpfilename, 1, None, '    1 a :- b.\n           ^ atom does not occur in any rule head:  b')),
             e.exception.args)

             
@test
def some_parts(stdout):
    """ this test mainly shows that control must be kept alive """
    control, handle = clingo_session(
            source='a. #program test_a(base). b. cannot(a) :- not a.',
            parts=[('base', ()), ('test_a', (clingo.Number(42),))],
            yield_=True)
    with handle:
        result = handle.get()
        test.truth(result.satisfiable)
        test.eq("a b", str(handle.model()))


@test
def from_clingo_main(stdout):
    run_clingo_plus_main(b"owkee. #program test_owkee(base).")
    test.startswith(stdout.getvalue(), "clingo+ version 5.7.1\nReading from stdin\n")
    test.contains(stdout.getvalue(), '-stdin.lp\n  test_owkee(base)Solving...\nAnswer: 1\nowkee\nSATISFIABLE')
    
        

@test
def simple_syntax_error_with_clingo_main(stdout, stderr):
    run_clingo_plus_main(b'plugin(".:errorplugin"). a')
    test.startswith(stdout.getvalue(), 'clingo+ version 5.7.1\nReading from stdin\nUNKNOWN')
    traceback = stderr.getvalue()
    should = """-stdin.lp", line 2
    1 plugin(".:errorplugin"). a
      ^ syntax error, unexpected EOF
aspselftest.plugins.messageparser.AspSyntaxError: syntax error, unexpected EOF
*** ERROR: (clingo+): syntax error
"""
    test.endswith(traceback, should)



@test
def run_a_succeeding_test(stdout, stderr):
    control, handle = clingo_session(
        source='a. #program test_a(base). cannot(a) :- not a.', yield_=True,
        label='with_tests', plugins=[testrunner_plugin, *default_plugins])
    test.eq(stdout.getvalue(), "<with_tests>\n  test_a(base)\n")
    test.eq(stderr.getvalue(), "")
    with handle:
        result = handle.get()
        test.truth(result.satisfiable)
        test.eq('a', str(handle.model()))


@test
def run_a_failing_test(stdout, stderr):
    with test.raises(AssertionError) as e:
        clingo_session(
            source='#program test_b(base). cannot(base).',
            plugins=[testrunner_plugin, *default_plugins])
    test.eq(stdout.getvalue(), "<string>\n  test_b(base)\n")
    test.eq(stderr.getvalue(), "")
    test.eq('cannot("N/A")' , str(e.exception))
    test.eq(['File <string>, line 1, in test_b(base).'] , e.exception.__notes__)


@test
def run_a_mixed_test(stdout, stderr):
    with test.raises(AssertionError) as e:
        clingo_session(
            source='a. #program test_a(base). cannot(a) :- not a. #program test_b(base). cannot(b).',
            label='two_tests', plugins=[errorplugin, testrunner_plugin, *default_plugins])
    test.eq(stdout.getvalue(), "<two_tests>\n  test_a(base)\n  test_b(base)\n")
    test.eq(stderr.getvalue(), "")
    test.eq('cannot(b)' , str(e.exception))
    test.eq(["File <two_tests>, line 1, in test_b(base)."] , e.exception.__notes__)


@test
def asp_test_with_error():
        clingo_session(
            source='a. #program test_a(base)',
            plugins=[testrunner_plugin, *default_plugins])
    