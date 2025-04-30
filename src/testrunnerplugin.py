import sys
import clingo.ast

import selftest
test =  selftest.get_tester(__name__)

from sessionng import clingo_session, default_plugins, Noop, run_clingo_plus_main


NA = clingo.String("N/A")


def testrunner_plugin(source=None, parts=None, yield_=None, plugins=(), label=None, **etc):

    _tests = {}

    def _filter_program(ast):
        if program := is_testprogram(ast):
            name, dependencies, filename, lineno = program
            _tests.setdefault(filename, []).append(program)

    def load(next, control):
        clingo.ast.parse_string(source, callback=_filter_program)
        for filename, tests in _tests.items():
            filename = f"<{label}>" if filename == '<string>' and label else filename
            print(filename)
            for testname, dependencies, _, lineno in tests:
                fulltestname = f"{testname}({', '.join(dependencies)})"
                print(" ", fulltestname, end='', flush=True)
                parts = ((testname, [NA for _ in dependencies]), *((d, []) for d in dependencies))
                _, handle = clingo_session(source=source, parts=parts, yield_=True, plugins=plugins[1:])
                print()
                with handle:
                    for model in handle:
                        if failures := list(model.context.symbolic_atoms.by_signature('cannot', 1)):
                            e = AssertionError(', '.join(str(f.symbol) for f in failures))
                            e.add_note(f"File {filename}, line {lineno}, in {fulltestname}.")
                            raise e

        next(control)

    return Noop, Noop, load, Noop, Noop


def is_testprogram(a):
    if a.ast_type == clingo.ast.ASTType.Program and a.name.startswith('test_'):
        loc = a.location.begin
        return a.name, [p.name for p in a.parameters], loc.filename, loc.line


@test
def run_a_succeeding_test(stdout, stderr):
    control, handle = clingo_session(
        source='a. #program test_a(base). cannot(a) :- not a.', yield_=True,
        label='with_tests', plugins=[testrunner_plugin, *default_plugins])
    test.eq(stdout.getvalue(), "<with_tests>\n  test_a(base)\n")
    test.eq(stderr.getvalue(), "")
    with handle:
        result = handle.get()
        test.truth(result.satisfiable)
        test.eq('a', str(handle.model()))


@test
def run_a_failing_test(stdout, stderr):
    with test.raises(AssertionError) as e:
        clingo_session(
            source='#program test_b(base). cannot(base).',
            plugins=[testrunner_plugin, *default_plugins])
    test.eq(stdout.getvalue(), "<string>\n  test_b(base)\n")
    test.eq(stderr.getvalue(), "")
    test.eq('cannot("N/A")' , str(e.exception))
    test.eq(['File <string>, line 1, in test_b(base).'] , e.exception.__notes__)


@test
def run_a_mixed_test(stdout, stderr):
    with test.raises(AssertionError) as e:
        clingo_session(
            source='a. #program test_a(base). cannot(a) :- not a. #program test_b(base). cannot(b).',
            label='two_tests', plugins=[testrunner_plugin, *default_plugins])
    test.eq(stdout.getvalue(), "<two_tests>\n  test_a(base)\n  test_b(base)\n")
    test.eq(stderr.getvalue(), "")
    test.eq('cannot(b)' , str(e.exception))
    test.eq(["File <two_tests>, line 1, in test_b(base)."] , e.exception.__notes__)