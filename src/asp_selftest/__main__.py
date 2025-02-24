
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
    run_asp_tests(*args.lpfile, base_programs=args.programs, hooks=args.processor)


# old stuff to keep old main alive for a while
def run_asp_tests(*files, base_programs=(), hooks=()):
    for program_file in files:
        name = getattr(program_file, 'name', str(program_file))
        print(f"Reading {name}.", flush=True)
        asp_code = program_file.read()
        from .runasptests import parse_and_run_tests
        from .tester import print_test_result
        for result in parse_and_run_tests(asp_code, base_programs, hooks=hooks):
            print_test_result(result)  # TODO doesn't parse_and_run_tests already call print_test_result?


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


