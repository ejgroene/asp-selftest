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
            _tests.setdefault(filename, []).append(program)

    def load(maincontrol, files):
        clingo.ast.parse_files(files, callback=_filter_program, logger=logger)
        for filename, tests in _tests.items():
            print("Testing", filename)
            for testname, dependencies, _, lineno in tests:
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
def testrunner_plugin_basics(tmp_path):
    testfile = write_file(tmp_path/'testfile.lp', """\
        a.
        #program test_a.
        cannot(a).
    """)

    _0, load, ground, solve = testrunner_plugin(simple_clingo_plugin)

    main_control = clingo.Control()
    with test.raises(AssertionError, "cannot(a)") as e:
        load(main_control, files=(testfile,))
    test.eq(e.exception.__notes__[0], f"File {testfile}, line 2, in test_a().")


@test
def testrunner_plugin_no_failures(tmp_path):
    testfile = write_file(tmp_path/'testfile.lp', """\
        #external a.
        #program test_a.
        cannot(a) :- a.
    """)

    _0, load, ground, solve = testrunner_plugin(simple_clingo_plugin)

    main_control = clingo.Control()
    load(main_control, files=(testfile,))
    ground(main_control, (('base', ()), ('test_a', ())))
    solve(main_control, False)
    # NB: both symbols below are in the symbol table, but both false
    test.eq('a', str(next(main_control.symbolic_atoms.by_signature('a', 0)).symbol))
    test.eq('cannot(a)', str(next(main_control.symbolic_atoms.by_signature('cannot', 1)).symbol))


