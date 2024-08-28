
""" Separate module to allow inspecting args before running selftests """

import argparse
import sys

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
    argparser.add_argument('--full-trace', help="Print full Python stack trace on error.", action='store_true')
    return argparser.parse_args(args)
