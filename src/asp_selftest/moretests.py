
""" Program argument and in-source test handling + some tests that introduce cyclic dependencies elsewhere. """

import os
import sys
import subprocess
import pathlib


import clingo
from clingo import Control


from .arguments import maybe_silence_tester
from .__main__ import clingo_plus


import selftest
test = selftest.get_tester(__name__)


VERSION = '.'.join(map(str,clingo.version()))


def spawn_clingo_plus(input="", arguments=[]):
    path = pathlib.Path(__file__).parent
    p = subprocess.run(["python", "-c", f"from asp_selftest.__main__ import clingo_plus; clingo_plus()"] + arguments,
        env=os.environ | {'PYTHONPATH': path},
        input=input,
        capture_output=True)
    return p


@test
def maybe_shutup_selftest(argv):
    argv += ['--silent']
    try:
        maybe_silence_tester()
    except AssertionError as e:
        test.startswith(str(e), 'In order to NOT run Python tests, Tester <Tester None created at:')
        test.endswith(str(e), 'must have been configured to NOT run tests.')
    # this indirectly tests if the code above actually threw the AssertionError
    test.eq(True, selftest.get_tester(None).option_get('run'))


@test
def main_entry_point_basics():
    p = spawn_clingo_plus(input=b"skaludicat. #program test_gotashparot(base).", arguments=['--run-asp-tests'])
    test.eq(b'', p.stderr)
    test.startswith(p.stdout.decode(), f"""\
clingo+ version {VERSION}
Reading from stdin
Testing stdin
  test_gotashparot(base)
Testing base
  base
Solving...""")
    test.contains(p.stdout.decode(), f"""\
skaludicat
SATISFIABLE

Models""", diff=test.diff)


@test
def simple_syntax_error_with_clingo_main():
    p = spawn_clingo_plus(b'plugin(".:errorplugin"). a', arguments=['--run-asp-tests'])
    test.startswith(p.stdout, f'clingo+ version {VERSION}\nReading from stdin\nUNKNOWN'.encode())
    traceback = p.stderr
    should = b"""-stdin.lp", line 2
    1 plugin(".:errorplugin"). a
      ^ syntax error, unexpected EOF
asp_selftest.plugins.messageparser.AspSyntaxError: syntax error, unexpected EOF
"""
    test.endswith(traceback, should, diff=test.diff)
    test.comp.contains(p.stdout, b"*** ERROR")
    test.comp.contains(traceback, b"*** ERROR")


@test
def clingo_drop_in_plus_tests(tmp_path, argv, stdout, stderr):
    f = tmp_path/'f.lp'
    f.write_text('a. #program test_ikel(base).\n')
    argv += [f.as_posix(), '--run-python-tests']  # we can not NOT run the Python tests here
    clingo_plus()
    s = iter(stdout.getvalue().splitlines())
    test.eq(f'clingo+ version {VERSION}', next(s))
    l = next(s)
    test.startswith(l, 'Reading from')
    test.endswith(l, 'f.lp')
    test.eq('Solving...', next(s))
    #test.eq('Answer: 1 (Time: 0.000s)', next(s))
    next(s)
    test.eq('a', next(s))
    test.eq('SATISFIABLE', next(s))
    test.eq('', next(s))
    test.eq('Models       : 1+', next(s))
    test.eq('Calls        : 1', next(s))
    l = next(s)
    test.contains(l, 'Time')
    test.contains(l, 'Solving:')
    test.contains(l, '1st Model:')
    test.contains(l, 'Unsat:')
    test.startswith(next(s), 'CPU Time     : 0.00')
    test.startswith(stderr.getvalue(), "")


@test
def syntax_errors_basics(tmp_path, argv, stdout, stderr):
    f = tmp_path/'f'
    f.write_text("a syntax error")
    argv += [f.as_posix(), '--run-python-tests']
    with test.raises(SyntaxError) as e:
        clingo_plus()
    out = stdout.getvalue()
    test.eq('syntax error, unexpected <IDENTIFIER>', e.exception.msg)
    test.contains(out, f"Reading from ...{f.as_posix()[-38:]}")
    err = stderr.getvalue()
    test.eq(err, '')


@test
def tester_runs_tests(tmp_path, argv, stdout, stderr):
    f = tmp_path/'f'
    f.write_text("""
    fact(a).
    #program test_fact(base).
    cannot("fact") :- not fact(a).
    models(1).
    """)
    argv += [f.as_posix(), '--run-asp-tests', '--run-python-tests']
    clingo_plus()
    test.contains(stdout.getvalue(), f"Testing {f}\n  test_fact(base)\nTesting base\n  base\n")
    test.startswith(stderr.getvalue(), "")


@test
def clingo_dropin_default_hook_tests(tmp_path, argv, stdout, stderr):
    f = tmp_path/'f'
    f.write_text("""
    fact(a).
    #program test_fact_1(base).
    cannot("fact 1") :- not fact(a).
    models(1).
    #program test_fact_2(base).
    cannot("fact 2") :- not fact(a).
    models(1).
    """)
    argv += [f.as_posix(), '--run-asp-tests', '--run-python-tests']
    clingo_plus()
    s = stdout.getvalue()
    test.contains(s, f"Testing {f}\n  test_fact_1(base)\n  test_fact_2(base)\nTesting base\n  base\n")
    test.startswith(stderr.getvalue(), "")


@test
def clingo_dropin_default_hook_errors(tmp_path, argv, stdout, stderr):
    f = tmp_path/'f'
    f.write_text("""syntax error """)
    argv += [f.as_posix(), '--run-python-tests']
    with test.raises(SyntaxError, "syntax error, unexpected <IDENTIFIER>") as e:
        clingo_plus()
    test.contains(stdout.getvalue(), """UNKNOWN\n
Models       : 0+""")
    test.eq(
        "    1 syntax error \n             ^^^^^ syntax error, unexpected <IDENTIFIER>",
        e.exception.text)
    test.eq(stderr.getvalue(), '')


@test
def access_python_script_functions(tmp_path, argv, stdout, stderr):
    f = tmp_path/'f'
    f.write_text("""
#script (python)
def my_func(a):
    return a
#end.
#program test_one.
something(@my_func("hello")).
models(1).
    """)
    argv += [f.as_posix(), '--run-asp-tests', '--run-python-tests']
    clingo_plus()
    s = stdout.getvalue()
    test.contains(s, f"Testing {f}\n  test_one()\n")
    test.startswith(stderr.getvalue(), "")


@test
def bug_read_stdin_and_solve_with_run_tests():
    # solving was prevented because stdin was read by the tester and gone for the next step
    p = spawn_clingo_plus(input=b"a. b. c.", arguments=['--run-python-tests'])
    test.contains(p.stdout, b"Answer: 1 (Time: ")
    test.contains(p.stdout, b"s)\na b c\nSATISFIABLE\n")
    p = spawn_clingo_plus(input=b"a. b. c.", arguments=[])
    test.contains(p.stdout, b"Answer: 1 (Time: ")
    test.contains(p.stdout, b"s)\na b c\nSATISFIABLE\n")
    p = spawn_clingo_plus(input=b"a. b. c.", arguments=['--run-python-tests', '--run-asp-tests'])
    test.contains(p.stdout, b"Answer: 1 (Time: ")
    test.contains(p.stdout, b"s)\na b c\nSATISFIABLE\n")
    p = spawn_clingo_plus(input=b"a. b. c.", arguments=['--run-asp-tests'])
    test.contains(p.stdout, b"Answer: 1 (Time: ")
    test.contains(p.stdout, b"s)\na b c\nSATISFIABLE\n")
    test.eq(b'', p.stderr)
