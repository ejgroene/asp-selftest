
""" Program argument and in-source test handling + some tests that introduce cyclic dependencies elsewhere. """

import io
import sys


import clingo
from clingo import Control


from .arguments import parse, maybe_silence_tester, parse_reify
from .__main__ import main, clingo_plus, asp_reify
from .application import MainApp
from .syntaxerrorhandler import SyntaxErrorHandler
from .tester import TesterHook
from .runasptests import parse_and_run_tests, ground_exc
from .utils import find_symbol
from .application import main_clingo_plus


import selftest
test = selftest.get_tester(__name__)


@test
def test_reify_args():
    args = parse_reify(['--include-source'])
    test.truth(args.include_source)


@test
def reify_entry_point(stdout, stdin, argv):
    argv += ['--include-source']
    class FU:
        def read(self):
            return 'rule(aap).'
    sys.stdin = FU()
    asp_reify()
    test.eq('rule(aap).\n#external aap.\n\n', stdout.getvalue())


@test
def reify_print_path(stdout, argv):
    argv += ['--print-include-path']
    asp_reify()
    test.endswith(stdout.getvalue(), "/src/asp_selftest\n")


@test
def use_own_python_function():
    t = parse_and_run_tests("""
#script (python)
def echo(message):
    return message
#end.

#program test_me(base).
hello(@echo("hi")).
models(1).
""")
    data = next(t)
    data.pop('filename')
    test.eq({'testname': 'test_me', 'models': 1}, data)
    # implicitly tested by the fact that it does not raise exception on @echo()
    test.eq([], list(t))


@test
def reraise_unknown_exceptinos():
    t = parse_and_run_tests("""
#script (python)
def exception_raiser():
    raise Exception("unknown")
#register(exception_raiser)
#end.

predicate(@exception_raiser()).
""")
    with test.raises(Exception, 'unknown'):
        next(t)


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
    stdin.write("a. #program test_a.")
    stdin.seek(0)
    main()
    response = stdout.getvalue()
    test.startswith(response, 'Reading <_io.StringIO')
    test.endswith(response, 'ASPUNIT: test_a:  1 model\n')


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
    f.write_text('a. #program test_ikel.\n')
    argv += [f.as_posix()]
    clingo_plus()
    s = stdout.getvalue().splitlines()
    test.eq('clingo+ version 5.7.1', s[0])
    test.startswith(s[1], 'Reading from')
    test.endswith(s[1], 'f.lp')
    test.eq('ASPUNIT: test_ikel:  1 model', s[2])
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
def warn_if_not_used_as_context():
    app = MainApp(handlers=[SyntaxErrorHandler()])
    with test.raises(
            AssertionError,
            "MainApp.main only to be called within a context manager") as e:
        app.main(Control(), [])
        app.check()


@test
def syntax_errors_basics(tmp_path):
    f = tmp_path/'f'
    f.write_text("a syntax error")
    with test.raises(SyntaxError) as e:
        with MainApp(handlers=[SyntaxErrorHandler()]) as app:
            app.main(Control(), [f.as_posix()])
            app.check()
    test.eq('syntax error, unexpected <IDENTIFIER>', e.exception.msg)


@test
def tester_runs_tests(tmp_path, stdout):
    f = tmp_path/'f'
    f.write_text("""
    fact(a).
    #program test_fact(base).
    cannot("fact") :- not fact(a).
    models(1).
    """)
    with MainApp(handlers=[TesterHook()]) as app:
        app.main(Control(), [f.as_posix()])
    test.eq('ASPUNIT: test_fact:  1 model\n',
            stdout.getvalue())


@test
def clingo_dropin_default_hook_tests(tmp_path, argv, stdout):
    f = tmp_path/'f'
    f.write_text("""
    fact(a).
    #program test_fact_1(base).
    cannot("fact 1") :- not fact(a).
    models(1).
    #program test_fact_2(base).
    cannot("fact 2") :- not fact(a).
    models(1).
    """)
    argv += [f.as_posix()]
    clingo_plus()
    s = stdout.getvalue()
    test.contains(s, 'ASPUNIT: test_fact_1:  1 model\n')
    test.contains(s, 'ASPUNIT: test_fact_2:  1 model\n')


@test
def clingo_dropin_default_hook_errors(tmp_path, argv, stdout):
    f = tmp_path/'f'
    f.write_text("""syntax error """)
    argv += [f.as_posix()]
    with test.raises(SyntaxError, "syntax error, unexpected <IDENTIFIER>") as e:
        clingo_plus()
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
something(@my_func("hello")).
models(1).
    """)
    argv += [f.as_posix()]
    clingo_plus()
    s = stdout.getvalue()
    test.contains(s, "ASPUNIT: test_one:  1 model")
    #test.contains(s, 'assert(models(1)) assert("hello")')


@test.fixture
def asp(code, name):
    name.write_text(code)
    yield name.as_posix()

@test.fixture
def with_asp(tmp_path, code, name):
    fname = tmp_path/name
    fname.write_text(code)
    yield fname.as_posix()

@test
def multiple_bases_must_not_fail_with_duplicate_base(tmp_path):
    ast = []
    with test.asp('g.', tmp_path/'g.lp') as g, \
         test.asp(f'#include "{g}". f.', tmp_path/'f.lp') as f:
            clingo.ast.parse_files([f], ast.append)
    test.eq(4, len(ast))
    test.eq('#program base.', str(ast[0]))  # both f.lp and g.lp have a base
    test.eq('g.',             str(ast[1]))
    test.eq('#program base.', str(ast[2]))  # both f.lp and g.lp have a base
    test.eq('f.',             str(ast[3]))
    c = Control()
    with MainApp(handlers=[TesterHook()]) as a:
        a.main(c, [f])
    test.eq('g', find_symbol(c, "g"))

#@test
def test_main_main(with_asp:("fail", 'f')):
    with test.raises(SystemExit, -1):
        main_clingo_plus(['base'], [with_asp], [])

