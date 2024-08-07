
""" Program argument and in-source test handling + some tests that introduce cyclic dependencies elsewhere. """

import selftest
import argparse
from .arguments import parse, parse_silent


# First of all, inspect --silent flag to silence tests
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
        assert not root.option_get('run'), "Tester must have been configured to NOT run tests."


test = selftest.get_tester(__name__)


@test
def check_arguments():
    args = parse(['filename.lp', 'morehere.lp'])
    test.eq(['filename.lp', 'morehere.lp'], args.lpfile)
    test.not_(args.silent)
    test.not_(args.full_trace)


@test
def check_usage_message():
    with test.stderr as s:
        with test.raises(SystemExit):
            parse([])
    test.eq("""usage: asp-selftest [-h] [--silent] [--full-trace] lpfile [lpfile ...]
asp-selftest: error: the following arguments are required: lpfile
""", s.getvalue(), diff=test.diff)


@test
def check_flags():
    args = parse(['required.lp', '--silent', '--full-trace'])
    test.truth(args.silent)
    test.truth(args.full_trace)



from .runasptests import local, register, format_symbols


@test
def register_asp_function():
    local.current_tester = None
    def f(a):
        pass
    test.eq(None, local.current_tester)
    register(f)
    test.eq(None, local.current_tester)
    fs = []
    class X:
        def add_function(self, f):
            fs.append(f)
    try:
        local.current_tester = X()
        register(f)
        test.eq(f, fs[0])
    finally:
        local.current_tester = None


@test
def register_asp_function_is_function(raises:(AssertionError, "'aap' must be a function")):
    register("aap")


from .runasptests import ground_and_solve, ground_exc
