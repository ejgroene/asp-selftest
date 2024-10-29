
""" Runs all tests in an ASP program.

    This module contains all 'mains', e.q. entry points as 
    defined in pyproject.toml.

    Tests are in moretests.py to keep to module importable with choice of running tests or not
"""

import sys


# this function is directly executed by the pip installed code wrapper, see pyproject.toml
def main():
    from .arguments import maybe_silence_tester
    maybe_silence_tester() # TODO somehow test this
    from .arguments import parse
    args = parse()
    #if not args.full_trace:
    #    sys.tracebacklimit = 0
    from .runasptests import run_asp_tests
    run_asp_tests(*args.lpfile, base_programs=args.programs, hooks=args.processor)


# this function is directly executed by pip installed code wrapper, see pyproject.toml
def clingo_plus_tests():
    from .arguments import maybe_silence_tester
    maybe_silence_tester() # TODO somehow test this
    from .arguments import parse_clingo_plus_args
    """ new all-in dropin replacement for Clingo WIP EXPERIMENTAL """
    """ Add --programs option + testing and ground/solve as stock Clingo as much as possible. """
    opts, remaining = parse_clingo_plus_args()
    from .application import main_main
    from .processors import SyntaxErrors
    from .tester import TesterHook
    main_main(opts.programs, remaining, hooks=[TesterHook(), SyntaxErrors()])

