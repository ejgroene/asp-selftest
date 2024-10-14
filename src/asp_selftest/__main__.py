
""" Runs all tests in an ASP program. """


# this function is directly executed by the pip installed code wrapper, see pyproject.toml
def main():
    import sys
    from .arguments import parse
    from .runasptests import run_asp_tests

    args = parse()

    if not args.full_trace:
        sys.tracebacklimit = 0

    run_asp_tests(*args.lpfile, base_programs=args.programs)


# this function is directly executed by pip installed code wrapper, see pyproject.toml
def clingo_plus_tests():
    from .processors import main
    main()


# this allows the code to also be run with python -m
if __name__ == '__main__':
    main()
