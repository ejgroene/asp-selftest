
""" Separate module to allow inspecting args before running selftests """

import argparse
import sys
import selftest



def maybe_silence_tester(argv=None):
    silent = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    silent.add_argument('--silent', help="Do not run my own in-source Python tests.", action='store_true')
    args, unknown = silent.parse_known_args(argv)
    if args.silent:
        try:
            # must be called first and can only be called once, but, when
            # we are imported from another app that also uses --silent, 
            # that app might already have called basic_config()
            # TODO testme
            selftest.basic_config(run=False)
        except AssertionError:
            root = selftest.get_tester(None)
            CR = '\n'
            assert not root.option_get('run'), "In order for --silent to work, " \
                f"Tester {root}{CR} must have been configured to NOT run tests."
    return unknown


def parse_plus_arguments(argv=None):
    argparser = argparse.ArgumentParser(description='Runs in-source ASP tests in given logic programs')
    argparser.add_argument('--run-tests', help="Run all selftests in ASP code.", action='store_true')
    return argparser.parse_known_args(argv)

