
""" Runs all tests in an ASP program.

    This module contains all 'mains', e.q. entry points as 
    defined in pyproject.toml.

    It also contains the tests.
"""

import sys

from clingo import clingo_main, Control


from .arguments import parse, parse_clingo_plus_args
from .runasptests import run_asp_tests
from .application import MainApp
from .processors import SyntaxErrors


# this function is directly executed by the pip installed code wrapper, see pyproject.toml
def main():
    args = parse()
    #if not args.full_trace:
    #    sys.tracebacklimit = 0
    run_asp_tests(*args.lpfile, base_programs=args.programs, hooks=args.processor)


# this function is directly executed by pip installed code wrapper, see pyproject.toml
def clingo_plus_tests():
    """ new all-in dropin replacement for Clingo WIP EXPERIMENTAL """
    """ Add --programs option + testing and ground/solve as stock Clingo as much as possible. """
    opts, remaining = parse_clingo_plus_args()
    opts.programs and print("Grounding programs:", opts.programs)
    app = MainApp(programs=opts.programs, hooks=[SyntaxErrors()])
    r = clingo_main(app, remaining)
    app.check()



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
    test.eq('Time         : 0.000s (Solving: 0.00s 1st Model: 0.00s Unsat: 0.00s)', s[9])
    test.eq('CPU Time     : 0.000s', s[10])


@test
def syntax_errors_basics(tmp_path):
    f = tmp_path/'f'
    f.write_text("a syntax error")
    from .application import MainApp
    from .processors import SyntaxErrors
    app = MainApp(hooks=[SyntaxErrors()])
    with test.raises(SyntaxError) as e:
        app.main(Control(), [f.as_posix()])
        app.check()
    test.eq('syntax error, unexpected <IDENTIFIER>', e.exception.msg)

