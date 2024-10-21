
""" Separate module to allow inspecting args before running selftests """

import argparse
import sys
import selftest


def maybe_silence_tester():
    args = parse_silent()
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


silent = argparse.ArgumentParser(add_help=False, exit_on_error=False)
silent.add_argument('--silent', help="Do not run my own in-source Python tests.", action='store_true')


def parse_silent(argv=None):
    args, unknown = silent.parse_known_args(argv)
    return args


def parse(args=None):
    argparser = argparse.ArgumentParser(
            parents=[silent],
            prog='asp-selftest',
            description='Runs in-source ASP tests in given logic programs')
    argparser.add_argument(
            'lpfile',
            help="File containing ASP and in-source tests. Default is STDIN.",
            type=argparse.FileType(),
            default=[sys.stdin],
            nargs='*')
    argparser.add_argument(
            '--programs',
            help="Additional programs to ground on top of 'base'.",
            default=(),
            nargs='*')
    argparser.add_argument(
            '--processor',
            help="Python '<module>:<function>' to invoke with the control after loading sources.",
            default=(),
            nargs='*')

    argparser.add_argument('--full-trace', help="Print full Python stack trace on error.", action='store_true')
    return argparser.parse_args(args)


def parse_clingo_plus_args(argv=None):
    args = argparse.ArgumentParser(
            parents = [silent],
            add_help = False,
            exit_on_error = False,
            allow_abbrev = False)
    args.add_argument('-p', '--programs', nargs='+', help="specify #program's to ground")
    return args.parse_known_args(argv)
