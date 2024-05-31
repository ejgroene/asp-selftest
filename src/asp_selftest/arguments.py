
""" Separate module to allow inspecting args before running selftests """

import argparse

def parse(args=None):
    argparser = argparse.ArgumentParser(
            prog='asp-selftest',
            description='Runs in-source ASP tests in given logic programs',
            exit_on_error=False)
    argparser.add_argument('lpfile', help="File containing ASP and in-source tests.", nargs='+')
    argparser.add_argument('--silent', help="Do not run my own in-source Python tests.", action='store_true')
    argparser.add_argument('--full-trace', help="Print full Python stack trace on error.", action='store_true')
    return argparser.parse_args(args)
