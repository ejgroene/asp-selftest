
""" Runs all tests in an ASP program.

    This module contains all 'mains', e.q. entry points as 
    defined in pyproject.toml.

    Tests are in moretests.py to keep to module importable with choice of running tests or not
"""

import sys


# this function is directly executed by pip installed code wrapper, see pyproject.toml
def clingo_plus():
    from .arguments import maybe_silence_tester
    maybe_silence_tester() # TODO somehow test this
    from .arguments import parse_clingo_plus_args
    """ new all-in dropin replacement for Clingo WIP EXPERIMENTAL """
    """ Add --programs option + testing and ground/solve as stock Clingo as much as possible. """
    plus_options, clingo_options = parse_clingo_plus_args()
    from .application import main_clingo_plus
    main_clingo_plus(clingo_options, programs=plus_options.programs)
    #import cProfile
    #with cProfile.Profile() as p:
    #    try:
    #        main_clingo_plus(clingo_options, programs=plus_options.programs)
    #    finally:
    #        p.dump_stats('profile.prof') # use snakeviz to view


def asp_reify(): # entry point
    from .arguments import maybe_silence_tester
    maybe_silence_tester()
    from .arguments import parse_reify
    from .reifyhandler import asp_reify
    """ Read ASP, interpreting reify()  and &reify{} predicates. """
    args = parse_reify()
    if args.print_include_path:
        from .reifyhandler import THEORY_PATH
        print(THEORY_PATH)
    else:
        asp_code = sys.stdin.read()
        reifies = asp_reify(asp_code)
        if args.include_source:
            print(asp_code)
        print(''.join(reifies))
