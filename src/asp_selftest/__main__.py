
""" Runs all tests in an ASP program. """

import argparse

argparser = argparse.ArgumentParser(prog='asp-selftest', description='Runs in-source ASP tests in given logic programs')
argparser.add_argument('lpfile', help="File containing ASP and in-source tests.", nargs='+')
argparser.add_argument('--silent', help="Do not run my own in-source Python tests.", action='store_true')
argparser.add_argument('--full-trace', help="Print full Python stack trace on error.", action='store_true')

args = argparser.parse_args()


import selftest
if args.silent:
    selftest.basic_config(run=False)
test = selftest.get_tester(__name__)


@test
def check_arguments():
    args = argparser.parse_args(['filename.lp', 'morehere.lp'])
    test.eq(['filename.lp', 'morehere.lp'], args.lpfile)
    test.not_(args.silent)
    test.not_(args.full_trace)


@test
def check_usage_message():
    with test.stderr as s:
        with test.raises(SystemExit):
            argparser.parse_args([])
    test.eq("""usage: asp-selftest [-h] [--silent] [--full-trace] lpfile [lpfile ...]
asp-selftest: error: the following arguments are required: lpfile
""", s.getvalue(), diff=test.diff)


@test
def check_flags():
    args = argparser.parse_args(['required.lp', '--silent', '--full-trace'])
    test.truth(args.silent)
    test.truth(args.full_trace)


if not args.full_trace:
    import sys
    sys.tracebacklimit = 0


import runasptests
runasptests.run_asp_tests(*args.lpfile)


