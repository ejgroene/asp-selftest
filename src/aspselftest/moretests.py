
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



@test
def maybe_shutup_selftest(argv):
    argv += ['--silent']
    try:
        maybe_silence_tester()
    except AssertionError as e:
        test.startswith(str(e), 'In order for --silent to work, Tester <Tester None created at:')
        test.endswith(str(e), 'must have been configured to NOT run tests.')
    # this indirectly tests if the code above actually threw the AssertionError
    test.eq(True, selftest.get_tester(None).option_get('run'))


@test
def main_entry_point_basics():
    path = pathlib.Path(__file__).parent
    p = subprocess.run(["python", "-c", f"from aspselftest.__main__ import clingo_plus; clingo_plus()", "--run-tests"],
        env=os.environ | {'PYTHONPATH': path},
        input=b"skaludicat. #program test_gotashparot(base).",
        capture_output=True)
    test.eq(b'', p.stderr)
    test.startswith(p.stdout.decode(), """\
clingo+ version 5.7.1
Reading from stdin
Testing -
  base()
  test_gotashparot(base)
Solving...
Answer: 1

SATISFIABLE

Models""", diff=test.diff)


@test
def clingo_drop_in_plus_tests(tmp_path, argv, stdout, stderr):
    f = tmp_path/'f.lp'
    f.write_text('a. #program test_ikel(base).\n')
    argv += [f.as_posix()]
    clingo_plus()
    s = iter(stdout.getvalue().splitlines())
    test.eq('clingo+ version 5.7.1', next(s))
    l = next(s)
    test.startswith(l, 'Reading from')
    test.endswith(l, 'f.lp')
    test.eq('Solving...', next(s))
    test.eq('Answer: 1', next(s))
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
    argv += [f.as_posix()]
    with test.raises(SyntaxError) as e:
        clingo_plus()
    out = stdout.getvalue()
    test.eq('syntax error, unexpected <IDENTIFIER>', e.exception.msg)
    test.contains(out, f"Reading from ...{f.as_posix()[-38:]}")
    err = stderr.getvalue()
    test.contains(err, f"UNHANDLED MESSAGE: code=MessageCode.RuntimeError, message: '{f}:1:3-9: error: syntax error, unexpected <IDENTIFIER>\\n'\n")


@test
def tester_runs_tests(tmp_path, argv, stdout, stderr):
    f = tmp_path/'f'
    f.write_text("""
    fact(a).
    #program test_fact(base).
    cannot("fact") :- not fact(a).
    models(1).
    """)
    argv += [f.as_posix(), '--run-tests']
    clingo_plus()
    test.contains(stdout.getvalue(), f"Testing {f}\n  base()\n  test_fact(base)\n")
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
    argv += [f.as_posix(), '--run-tests']
    clingo_plus()
    s = stdout.getvalue()
    test.contains(s, f"Testing {f}\n  base()\n  test_fact_1(base)\n  test_fact_2(base)\n")
    test.startswith(stderr.getvalue(), "")


@test
def clingo_dropin_default_hook_errors(tmp_path, argv, stdout, stderr):
    f = tmp_path/'f'
    f.write_text("""syntax error """)
    argv += [f.as_posix()]
    with test.raises(SyntaxError, "syntax error, unexpected <IDENTIFIER>") as e:
        clingo_plus()
    test.contains(stdout.getvalue(), """UNKNOWN\n
Models       : 0+""")
    test.eq(
        "    1 syntax error \n             ^^^^^ syntax error, unexpected <IDENTIFIER>",
        e.exception.text)
    test.eq(stderr.getvalue(), f"UNHANDLED MESSAGE: code=MessageCode.RuntimeError, message: '{f}:1:8-13: error: syntax error, unexpected <IDENTIFIER>\\n'\n")

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
    argv += [f.as_posix(), '--run-tests']
    clingo_plus()
    s = stdout.getvalue()
    test.contains(s, f"Testing {f}\n  base()\n  test_one()\n")
    test.startswith(stderr.getvalue(), "")


@test.fixture
def asp(code, name):
    name.write_text(code)
    yield name.as_posix()

@test.fixture
def with_asp(tmp_path, code, name):
    fname = tmp_path/name
    fname.write_text(code)
    yield fname.as_posix()
