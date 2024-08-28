
""" Runs all tests in an ASP program. """


# this function is directly executed by the pip installed code wrapper
def main():
    import sys
    from .arguments import parse
    from .runasptests import run_asp_tests

    args = parse()

    if not args.full_trace:
        sys.tracebacklimit = 0

    run_asp_tests(*args.lpfile, base_programs=args.programs)


# this allows the code to also be run with python -m
if __name__ == '__main__':
    main()
