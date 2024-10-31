
""" Program argument and in-source test handling + some tests that introduce cyclic dependencies elsewhere. """

import argparse
import io

from clingo import Control

from .arguments import parse, parse_silent, maybe_silence_tester
from .__main__ import main, clingo_plus_tests
from .application import MainApp
from .processors import SyntaxErrors
from .tester import TesterHook
from .runasptests2 import parse_and_run_tests, ground_exc

from .tester import local, register, format_symbols


import selftest
test = selftest.get_tester(__name__)


@test
def register_python_function():
    t = parse_and_run_tests("""
#script (python)
def repeat(message):
    return message
register(repeat)
#end.

#program test_me(base).
assert(@all(@repeat("hi"))).
assert(@models(1)).
""")
    test.eq([('base', {'asserts': set(), 'models': 1}),
             ('test_me', {'asserts': {'assert(models(1))', 'assert("hi")'}, 'models': 1})], list(t))


@test
def reraise_unknown_exceptinos():
    t = parse_and_run_tests("""
#script (python)
def exception_raiser():
    raise Exception("unknown")
register(exception_raiser)
#end.

predicate(@exception_raiser()).
""")
    with test.raises(Exception, 'unknown'):
        next(t)


@test
def extra_source():
    c = ground_exc("a.", extra_src='b.')
    test.eq('a', str(next(c.symbolic_atoms.by_signature('a', 0)).symbol))
    test.eq('b', str(next(c.symbolic_atoms.by_signature('b', 0)).symbol))


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


@test
def main_entry_point_basics(stdin, stdout, argv):
    stdin.write("a.")
    stdin.seek(0)
    main()
    response = stdout.getvalue()
    test.startswith(response, 'Reading <_io.StringIO')
    test.endswith(response, 'ASPUNIT: base:  0 asserts,  1 model\n')


#@test  # --processor no longer supported
def main_entry_processing_hook(stdin, stdout, argv):
    argv += ['--processor', 'asp_selftest:test_hook']  # test_hook is in __init__.py
    stdin.write("a.\n")
    stdin.seek(0)
    main()
    response = stdout.getvalue()
    test.startswith(response, 'Reading <_io.StringIO')
    test.endswith(response, 'ASPUNIT: base:  2 asserts,  1 model\n')


@test
def clingo_drop_in_plus_tests(tmp_path, argv, stdout):
    f = tmp_path/'f.lp'
    f.write_text('a.\n')
    argv += [f.as_posix()]
    clingo_plus_tests()
    s = stdout.getvalue().splitlines()
    test.eq('clingo+tests version 5.7.1', s[0])
    test.startswith(s[1], 'Reading from')
    test.endswith(s[1], 'f.lp')
    test.eq('ASPUNIT: base:  0 asserts,  1 model', s[2])
    test.eq('Solving...', s[3])
    test.eq('Answer: 1', s[4])
    test.eq('a', s[5])
    test.eq('SATISFIABLE', s[6])
    test.eq('', s[7])
    test.eq('Models       : 1+', s[8])
    test.eq('Calls        : 1', s[9])
    test.contains(s[10], 'Time')
    test.contains(s[10], 'Solving:')
    test.contains(s[10], '1st Model:')
    test.contains(s[10], 'Unsat:')
    test.startswith(s[11], 'CPU Time     : 0.00')


@test
def syntax_errors_basics(tmp_path):
    f = tmp_path/'f'
    f.write_text("a syntax error")
    app = MainApp(hooks=[SyntaxErrors()])
    with test.raises(SyntaxError) as e:
        app.main(Control(), [f.as_posix()])
        app.check()
    test.eq('syntax error, unexpected <IDENTIFIER>', e.exception.msg)


@test
def tester_runs_tests(tmp_path, stdout):
    f = tmp_path/'f'
    f.write_text("""
    fact(a).
    #program test_fact(base).
    assert(@all("fact")) :- fact(a).
    assert(@models(1)).
    """)
    app = MainApp(hooks=[TesterHook()])
    app.main(Control(), [f.as_posix()])
    test.eq('ASPUNIT: base:  0 asserts,  1 model\nASPUNIT: test_fact:  2 asserts,  1 model\n',
            stdout.getvalue())


@test
def clingo_dropin_default_hook_tests(tmp_path, argv, stdout):
    f = tmp_path/'f'
    f.write_text("""
    fact(a).
    #program test_fact_1(base).
    assert(@all("fact")) :- fact(a).
    assert(@models(1)).
    #program test_fact_2(base).
    assert(@all("fact")) :- fact(a).
    assert(@models(1)).
    """)
    argv += [f.as_posix()]
    clingo_plus_tests()
    s = stdout.getvalue()
    test.contains(s, 'ASPUNIT: test_fact_1:  2 asserts,  1 model\n')
    test.contains(s, 'ASPUNIT: test_fact_2:  2 asserts,  1 model\n')


@test
def clingo_dropin_default_hook_errors(tmp_path, argv, stdout):
    f = tmp_path/'f'
    f.write_text("""syntax error """)
    argv += [f.as_posix()]
    with test.raises(SyntaxError, "syntax error, unexpected <IDENTIFIER>") as e:
        clingo_plus_tests()
    test.contains(stdout.getvalue(), """UNKNOWN\n
Models       : 0+""")
    test.eq(
        "    1 syntax error \n             ^^^^^ syntax error, unexpected <IDENTIFIER>",
        e.exception.text)

@test
def access_python_script_functions(tmp_path, argv, stdout):
    f = tmp_path/'f'
    f.write_text("""
#script (python)
def my_func(a):
    return a
#end.
#program test_one.
assert(@all(@my_func("hello"))).
assert(@models(1)).
    """)
    argv += [f.as_posix()]
    clingo_plus_tests()
    s = stdout.getvalue()
    test.contains(s, "ASPUNIT: test_one:  2 asserts,  1 model")
    #test.contains(s, 'assert(models(1)) assert("hello")')
