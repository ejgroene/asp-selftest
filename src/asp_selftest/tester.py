import sys
import io
import selftest
test = selftest.get_tester(__name__)


from .runasptests import (run_asp_tests,
                          read_programs,
                          print_test_result,
                          prog_with_dependencies,
                          Tester as OrgTester)


def log(*a, **k):
    print(*a, file=sys.stderr, **k)


class Tester:

    def __init__(self):
        self.programs = {}


    def parse(self, prev, ctl, files, on_ast):
        def filter(a):
            if p := is_program(a):
                name, dependencies = p
                self.programs[name] = [(d, []) for d in dependencies]
            on_ast(a)
        prev(ctl, files, filter)


    def ground(self, prev, ctl, base_parts, context):
        tester = OrgTester()
        ctl.register_observer(tester)
        for prog_name, dependencies in self.programs.items():
            if not prog_name.startswith('test_'):
                continue
            parts = base_parts + list(prog_with_dependencies(self.programs, prog_name, dependencies))
            try:
                ctl.cleanup()
                tester.reset(prog_name)
                ctl.ground(parts, context=tester)  # partial contexts needs more work TODO
                # we use stdout capture of selftest because it captures output from subprocesses etc
                with test.stdout as s:
                    ctl.solve(on_model=tester.on_model)
                    assert 'error' not in s.getvalue()
                print_test_result(prog_name, tester.report())
            except Exception as e:
                e.add_note(f"Error while running:  {prog_name}.")
                raise e from None
        tester.disable()
        prev(ctl, base_parts, context)


from clingo.ast import ASTType

def is_program(a):
    if a.ast_type == ASTType.Program:
        return a.name, [p.name for p in a.parameters]
