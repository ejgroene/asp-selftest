
""" Runs all tests in an ASP program.

    This module contains all 'mains', e.q. entry points as 
    defined in pyproject.toml.

    Tests are in moretests.py to keep to module importable with choice of running tests or not
"""

import sys


# this function is directly executed by pip installed code wrapper, see pyproject.toml
def clingo_plus():

    from .arguments import maybe_silence_tester
    remaining = maybe_silence_tester()

    from .arguments import parse_plus_arguments
    args, remaining = parse_plus_arguments(remaining)

    from .session2 import clingo_main_session
    clingo_main_session(run_tests=args.run_asp_tests, arguments=remaining)
    
    #import cProfile
    #with cProfile.Profile() as p:
    #    try:
    #        main_clingo_plus(clingo_options, programs=plus_options.programs)
    #    finally:
    #        p.dump_stats('profile.prof') # use snakeviz to view
