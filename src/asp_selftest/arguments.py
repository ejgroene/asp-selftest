
""" Separate module to allow inspecting args before running selftests """

import argparse
import sys
import selftest


silent = argparse.ArgumentParser(add_help=False, exit_on_error=False)
silent.add_argument('--run-python-tests', help="Also run in-source Python tests.", action='store_true')


def maybe_silence_tester(argv=None):
    args, unknown = silent.parse_known_args(argv)
    if not args.run_python_tests:
        try:
            # must be called first and can only be called once, but, when
            # we are imported from another app that also uses --silent, 
            # that app might already have called basic_config()
            # TODO testme
            selftest.basic_config(run=False)
        except AssertionError:
            root = selftest.get_tester(None)
            CR = '\n'
            assert not root.option_get('run'), "In order to NOT run Python tests, " \
                f"Tester {root}{CR} must have been configured to NOT run tests."
    return unknown


def parse_plus_arguments(argv=None):
    argparser = argparse.ArgumentParser(
            parents=[silent],
            add_help=False,
            exit_on_error=False,
            description='Runs in-source ASP tests in given logic programs, on top of standard clingo.',
            epilog="Clingo options below.\n")
    argparser.add_argument('--run-asp-tests', help="Run all selftests in ASP code.", action='store_true')
    # we try to make the --help as compatible with Clingo as possible
    argparser.add_argument('-h', '--help', help="Show all info on arguments.", type=int, nargs='?', choices=(1,2,3), const=1, default=None)
    args, unknown = argparser.parse_known_args(argv)
    if args.help:
        argparser.print_help()
        unknown.insert(0, f'--help={args.help}') # pass it to Clingo as well
    return args, unknown

