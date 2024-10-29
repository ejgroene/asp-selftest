
""" Runs all tests in an ASP program.

    This module contains all 'mains', e.q. entry points as 
    defined in pyproject.toml.

    It also contains the tests.
"""

import sys

from clingo import clingo_main, Control


from .arguments import parse, parse_clingo_plus_args
from .runasptests import run_asp_tests
from .application import MainApp, main_main
from .processors import SyntaxErrors
from .tester import Tester



# this function is directly executed by the pip installed code wrapper, see pyproject.toml
def main():
    from .arguments import maybe_silence_tester
    maybe_silence_tester() # TODO somehow test this
    args = parse()
    #if not args.full_trace:
    #    sys.tracebacklimit = 0
    run_asp_tests(*args.lpfile, base_programs=args.programs, hooks=args.processor)


# this function is directly executed by pip installed code wrapper, see pyproject.toml
def clingo_plus_tests():
    from .arguments import maybe_silence_tester
    maybe_silence_tester() # TODO somehow test this
    """ new all-in dropin replacement for Clingo WIP EXPERIMENTAL """
    """ Add --programs option + testing and ground/solve as stock Clingo as much as possible. """
    opts, remaining = parse_clingo_plus_args()
    main_main(opts.programs, remaining, hooks=[Tester(), SyntaxErrors()])



import selftest
test = selftest.get_tester(__name__)


@test
def main_entry_point_basics(stdin, stdout, argv):
    stdin.write("a.")
    stdin.seek(0)
    main()
    response = stdout.getvalue()
    test.startswith(response, 'Reading <_io.StringIO')
    test.endswith(response, 'ASPUNIT: base:  0 asserts,  1 model\n')


@test
def main_entry_processing_hook(stdin, stdout, argv):
    argv += ['--processor', 'asp_selftest:test_hook']  # test_hook is in __init__.py
    stdin.write("a.\n")
    stdin.seek(0)
    main()
    response = stdout.getvalue()
    test.startswith(response, 'Reading <_io.StringIO')
    test.endswith(response, 'ASPUNIT: base:  2 asserts,  1 model\n')


@test
def clingo_drop_in_plus_tests(tmp_path, argv, stdout):
    f = tmp_path/'f.lp'
    f.write_text('a.\n')
    argv += [f.as_posix()]
    clingo_plus_tests()
    s = stdout.getvalue().splitlines()
    test.eq('clingo+tests version 5.7.1', s[0])
    test.startswith(s[1], 'Reading from')
    test.endswith(s[1], 'f.lp')
    test.eq('Solving...', s[2])
    test.eq('Answer: 1', s[3])
    test.eq('a', s[4])
    test.eq('SATISFIABLE', s[5])
    test.eq('', s[6])
    test.eq('Models       : 1+', s[7])
    test.eq('Calls        : 1', s[8])
    test.contains(s[9], 'Time')
    test.contains(s[9], 'Solving:')
    test.contains(s[9], '1st Model:')
    test.contains(s[9], 'Unsat:')
    test.startswith(s[10], 'CPU Time     : 0.00')


@test
def syntax_errors_basics(tmp_path):
    f = tmp_path/'f'
    f.write_text("a syntax error")
    app = MainApp(hooks=[SyntaxErrors()])
    with test.raises(SyntaxError) as e:
        app.main(Control(), [f.as_posix()])
        app.check()
    test.eq('syntax error, unexpected <IDENTIFIER>', e.exception.msg)


@test
def tester_runs_tests(tmp_path):
    f = tmp_path/'f'
    f.write_text("""
    fact(a).
    #program test_fact(base).
    assert(@all("fact")) :- fact(a).
    assert(@models(1)).
    """)
    app = MainApp(hooks=[Tester()])
    app.main(Control(), [f.as_posix()])


@test
def clingo_dropin_default_hook_tests(tmp_path, argv, stdout):
    f = tmp_path/'f'
    f.write_text("""
    fact(a).
    #program test_fact_1(base).
    assert(@all("fact")) :- fact(a).
    assert(@models(1)).
    #program test_fact_2(base).
    assert(@all("fact")) :- fact(a).
    assert(@models(1)).
    """)
    argv += [f.as_posix()]
    clingo_plus_tests()
    s = stdout.getvalue()
    test.contains(s, 'ASPUNIT: test_fact_1:  2 asserts,  1 model\n')
    test.contains(s, 'ASPUNIT: test_fact_2:  2 asserts,  1 model\n')


@test
def clingo_dropin_default_hook_errors(tmp_path, argv, stdout, stderr):
    f = tmp_path/'f'
    f.write_text("""syntax error """)
    argv += [f.as_posix()]
    with test.raises(SyntaxError, "syntax error, unexpected <IDENTIFIER>"):
        clingo_plus_tests()
    test.contains(stdout.getvalue(), """UNKNOWN\n
Models       : 0+""")
    test.contains(stderr.getvalue(), """1 syntax error 
             ^^^^^ syntax error, unexpected <IDENTIFIER>""")

@test
def access_python_script_functions(tmp_path, argv, stdout):
    f = tmp_path/'f'
    f.write_text("""
#script (python)
def my_func(a):
    return a
#end.
#program test_one.
assert(@all(@my_func("hello"))).
assert(@models(1)).
    """)
    argv += [f.as_posix()]
    clingo_plus_tests()
    s = stdout.getvalue()
    test.contains(s, "ASPUNIT: test_one:  2 asserts,  1 model")
    #test.contains(s, 'assert(models(1)) assert("hello")')
