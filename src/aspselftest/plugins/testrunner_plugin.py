import sys
import clingo.ast

import selftest
test =  selftest.get_tester(__name__)

from .misc import Noop, NA, write_file
from ..session import clingo_session_base



def testrunner_plugin(next, **etc):
    """ Runs all tests in every file separately, during loading. """

    logger, _load, ground, solve = next(**etc)

    _tests = {}

    def _filter_program(ast):
        if program := is_testprogram(ast):
            name, dependencies, filename, lineno = program
            tests = _tests.setdefault(filename, {})
            if name in tests:
                raise AssertionError(f"Duplicate test: {name!r} in {filename}.")
            tests[name] = (dependencies, lineno)

    def load(maincontrol, files):
        clingo.ast.parse_files(files, callback=_filter_program, logger=logger)
        for filename, tests in _tests.items():
            print("Testing", filename)
            for testname, (dependencies, lineno) in tests.items():
                fulltestname = f"{testname}({', '.join(dependencies)})"
                parts = [(testname, [NA for _ in dependencies]), *((d, []) for d in dependencies)]
                print(" ", fulltestname, end='', flush=True)

                sublogger, subload, subground, subsolve = next(**etc)
                subcontrol = clingo.Control(logger=sublogger)
                subload(subcontrol, files=(filename,))
                subground(subcontrol, parts=parts)

                with subsolve(subcontrol, yield_=True) as models:
                    for model in models:
                        if failures := list(model.context.symbolic_atoms.by_signature('cannot', 1)):
                            e = AssertionError(', '.join(str(f.symbol) for f in failures))
                            e.add_note(f"File {filename}, line {lineno}, in {fulltestname}.")
                            print()
                            raise e
                print()
        _load(maincontrol, files)
    return logger, load, ground, solve


def is_testprogram(a):
    if a.ast_type == clingo.ast.ASTType.Program and a.name.startswith('test_'):
        loc = a.location.begin
        return a.name, [p.name for p in a.parameters], loc.filename, loc.line


def simple_clingo_plugin():
    def load(control, files):
        control.load(files[0])
    def ground(control, parts):
        control.ground(parts=parts)
    def solve(control, yield_):
        return control.solve(yield_=yield_)
    return None, load, ground, solve

@test
def testrunner_plugin_basics(tmp_path, stdout):
    testfile = write_file(tmp_path/'testfile.lp', """\
        #program test_a.
        cannot("I fail").
    """)

    _0, load, ground, solve = testrunner_plugin(simple_clingo_plugin)

    main_control = clingo.Control()
    with test.raises(AssertionError, 'cannot("I fail")') as e:
        load(main_control, files=(testfile,))
    test.eq(e.exception.__notes__[0], f"File {testfile}, line 1, in test_a().")
    test.eq(stdout.getvalue(), f"Testing {testfile}\n  test_a()\n")


@test
def testrunner_plugin_no_failures(tmp_path, stdout):
    testfile = write_file(tmp_path/'testfile.lp', """\
        a.
        #program test_a(base).
        cannot(a) :- not a.
    """)

    _, load, ground, solve = testrunner_plugin(simple_clingo_plugin)

    main_control = clingo.Control()
    load(main_control, files=(testfile,))
    test.eq(stdout.getvalue(), f"Testing {testfile}\n  test_a(base)\n")

    ground(main_control, (('base', ()), ('test_a', ())))
    test.eq('a', str(next(main_control.symbolic_atoms.by_signature('a', 0)).symbol))


@test
def run_tests_per_included_file_separately(tmp_path, stdout):
    part_a = write_file(tmp_path/'part_a.lp',
        f'#program test_a.')
    part_b = write_file(tmp_path/'part_b.lp',
        f'#include "{part_a}".  #program test_b.')
    part_c = write_file(tmp_path/'part_c.lp',
        f'#include "{part_b}".  #include "{part_a}".  #program test_c.')

    _, load, ground, solve = testrunner_plugin(simple_clingo_plugin)
    main_control = clingo.Control()
    load(main_control, files=(part_c,))
    out = stdout.getvalue()
    test.contains(out, f"""\
Testing {part_a}
  test_a()
Testing {part_b}
  test_b()
Testing {part_c}
  test_c()""")


# TEST taken from runasptests.py


def parse_and_run_tests(asp_code, base_programs=(), hooks=()):
    with test.tmp_path as p:
        inputfile = write_file(p/'inputfile.lp', asp_code)
        _, load, ground, _ = testrunner_plugin(simple_clingo_plugin)
        main_control = clingo.Control()
        load(main_control, files=(inputfile,))
    

@test
def check_for_duplicate_test():
    with test.raises(Exception) as e:
        parse_and_run_tests(""" #program test_a. \n #program test_a. """)
    test.startswith(str(e.exception), "Duplicate test: 'test_a' in ")
