
""" Program argument and in-source test handling + some tests that introduce cyclic dependencies elsewhere. """

import selftest
import argparse
import io

from .arguments import parse, parse_silent, maybe_silence_tester


test = selftest.get_tester(__name__)


@test
def check_arguments(tmp_path):
    f = tmp_path/'filename.lp'
    m = tmp_path/'morehere.lp'
    f.write_bytes(b'')
    m.write_bytes(b'')
    args = parse([f.as_posix(), m.as_posix()])
    test.isinstance(args.lpfile[0], io.TextIOBase)
    test.isinstance(args.lpfile[1], io.TextIOBase)
    test.not_(args.silent)
    test.not_(args.full_trace)


@test
def check_usage_message():
    with test.stderr as s:
        with test.raises(SystemExit):
            parse(['-niks'])
    test.eq('usage: asp-selftest [-h] [--silent] [--programs [PROGRAMS ...]] '
            '[--processor [PROCESSOR ...]] '
            '[--full-trace] [lpfile ...] '
            "asp-selftest: error: unrecognized arguments: -niks",
            ' '.join(s.getvalue().split()), diff=test.diff) # split/join to remove formatting spaces


@test
def check_flags():
    args = parse(['--silent', '--full-trace', '--processor', 'asp_selftest.test_hook'])
    test.truth(args.silent)
    test.truth(args.full_trace)
    test.eq(['asp_selftest.test_hook'], args.processor)



from .runasptests import local, register, format_symbols


@test
def register_asp_function():
    local.current_tester = None
    def f(a):
        test.eq(a, 'hello')
    test.eq(None, local.current_tester)
    register(f)
    test.eq(None, local.current_tester)
    fs = []
    class X:
        def add_function(self, f):
            fs.append(f)
            f('hello')
    try:
        local.current_tester = X()
        register(f)
        test.eq(f, fs[0])
    finally:
        local.current_tester = None


@test
def register_asp_function_is_function(raises:(AssertionError, "'aap' must be a function")):
    register("aap")


@test
def maybe_shutup_selftest(argv):
    argv += ['--silent']
    try:
        maybe_silence_tester()
    except AssertionError as e:
        test.startswith(str(e), 'In order for --silent to work, Tester <Tester None created at:')
        test.endswith(str(e), 'must have been configured to NOT run tests.')
    # this indirectly tests if the code above actually threw the AssertionError
    test.eq(True, selftest.get_tester(None).option_get('run'))

