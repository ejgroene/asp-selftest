import sys
import clingo.ast

import selftest
test =  selftest.get_tester(__name__)

from .misc import Noop, NA
from ..session import clingo_session_base



def testrunner_plugin(source=None, parts=None, yield_=None,
                      plugins=(), label=None, logger=None, **etc):

    _tests = {}

    def _filter_program(ast):
        if program := is_testprogram(ast):
            name, dependencies, filename, lineno = program
            _tests.setdefault(filename, []).append(program)

    def load(next, control, source, files):
        assert not source, source
        clingo.ast.parse_files(files, callback=_filter_program, logger=logger)
        for filename, tests in _tests.items():
            filename = f"<{label}>" if filename == '<string>' and label else filename
            print(filename)
            for testname, dependencies, _, lineno in tests:
                fulltestname = f"{testname}({', '.join(dependencies)})"
                parts = [(testname, [NA for _ in dependencies]), *((d, []) for d in dependencies)]
                print(" ", fulltestname, end='', flush=True)
                plgns = [p for p in plugins if p != testrunner_plugin]
                _, handle = clingo_session_base(source=source, files=files, parts=parts, yield_=True, plugins=plgns)
                print()
                with handle:
                    for model in handle:
                        if failures := list(model.context.symbolic_atoms.by_signature('cannot', 1)):
                            e = AssertionError(', '.join(str(f.symbol) for f in failures))
                            e.add_note(f"File {filename}, line {lineno}, in {fulltestname}.")
                            raise e

        next(control, source, files)

    return Noop, Noop, load, Noop, Noop


def is_testprogram(a):
    if a.ast_type == clingo.ast.ASTType.Program and a.name.startswith('test_'):
        loc = a.location.begin
        return a.name, [p.name for p in a.parameters], loc.filename, loc.line

