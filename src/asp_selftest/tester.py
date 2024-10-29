import sys
import io
import selftest
test = selftest.get_tester(__name__)


from .runasptests import (run_asp_tests,
                          read_programs,
                          print_test_result,
                          prog_with_dependencies,
                          Tester as OrgTester)


class CompoundContext:
    """ Clingo looks up functions in __main__ OR in context; we need both.
        (Functions defined in #script land in __main__)
    """

    def __init__(self, *contexts):
        self._contexts = contexts

    def __getattr__(self, name):
        for c in self._contexts:
            if f := getattr(c, name, None):
                return f
        return getattr(sys.modules['__main__'], name)


class TesterHook:

    def __init__(this):
        this.programs = {}
        this.ast = []   # we keep a copy of the ast to load it for each test


    def parse(this, self, ctl, files, on_ast):
        def filter(a):
            if p := is_program(a):
                name, dependencies = p
                this.programs[name] = [(d, []) for d in dependencies]
            on_ast(a)
            this.ast.append(a)
        self.parse(ctl, files, filter)


    def ground(this, self, ctl, base_parts, context):
        for prog_name, dependencies in this.programs.items():
            if not prog_name.startswith('test_'):
                continue
            parts = base_parts + list(prog_with_dependencies(this.programs, prog_name, dependencies))
            try:
                tester = OrgTester()
                # play nice with other hooks; maybe also add original arguments?
                control = clingo.Control(logger=self.logger, message_limit=self.message_limit)
                control.register_observer(tester)
                self.load(control, this.ast)
                self.ground(control, parts, context=CompoundContext(tester, context))
                self.solve(control, on_model=tester.on_model)
                print_test_result(prog_name, tester.report())
            except Exception as e:
                e.add_note(f"Error while running:  {prog_name}.")
                raise e from None
        self.ground(ctl, base_parts, context)


from clingo.ast import ASTType

def is_program(a):
    if a.ast_type == ASTType.Program:
        return a.name, [p.name for p in a.parameters]


import clingo
@test
def we_CAN_NOT_i_repeat_NOT_reuse_control():
    c = clingo.Control()
    c.add("a. #program p1. p(1). #program p2. p(2).")
    c.ground()
    test.eq(['a'], [str(s.symbol) for s in c.symbolic_atoms])
    c.cleanup()
    c.ground((('base', ()), ('p1', ())))
    test.eq(['a', 'p(1)'], [str(s.symbol) for s in c.symbolic_atoms])
    c.cleanup()
    c.ground((('base', ()), ('p2', ())))
    # p(1) should be gone
    test.eq(['a', 'p(1)', 'p(2)'], [str(s.symbol) for s in c.symbolic_atoms])

