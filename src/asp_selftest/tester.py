
import sys
import io
import collections
import shutil
import itertools
import clingo
import threading
import inspect
import unittest.mock as mock

import selftest
test = selftest.get_tester(__name__)


SymbolTypeFunction = clingo.SymbolType.Function

from .session import CompoundContext


def has_name(symbol, name):
   return symbol.type == SymbolTypeFunction and symbol.name == name


def print_test_result(result):
    name = result['testname']
    asserts = result['asserts']
    models = result['models']
    print(f"ASPUNIT: {name}: ", end='', flush=True)
    print(f" {len(asserts)} asserts,  {models} model{'s' if models>1 else ''}")


def prog_with_dependencies(programs, name, dependencies):
    yield name, [clingo.Number(42) for _ in dependencies]
    for dep, args in dependencies:
        assert dep in programs, f"Dependency {dep} of {name} not found."
        formal_args = programs.get(dep, [])
        formal_names = list(a[0] for a in formal_args)
        if len(args) != len(formal_names):
            raise Exception(f"Argument mismatch in {name!r} for dependency {dep!r}. Required: {formal_names}, given: {args}.")
        yield dep, [clingo.Number(a) for a in args]


CR = '\n' # trick to support old python versions that do not accecpt \ in f-strings
def batched(iterable, n):
    """ not in python < 3.12 """
    # batched('ABCDEFG', 3) → ABC DEF G
    if n < 1:
        raise ValueError('n must be at least one')
    iterator = iter(iterable)
    while batch := tuple(itertools.islice(iterator, n)):
        yield batch

@test
def batch_it():
    test.eq([], list(batched([], 1)))
    test.eq([(1,)], list(batched([1], 1)))
    test.eq([(1,),(2,)], list(batched([1,2], 1)))
    test.eq([(1,)], list(batched([1], 2)))
    test.eq([(1,2)], list(batched([1,2], 2)))
    test.eq([(1,2), (3,)], list(batched([1,2,3], 2)))
    with test.raises(ValueError, 'n must be at least one'):
        list(batched([], 0))


def format_symbols(symbols):
    symbols = sorted(str(s).strip() for s in symbols)
    if len(symbols) > 0:
        col_width = (max(len(w) for w in symbols)) + 2
        width, h = shutil.get_terminal_size((120, 20))
        cols = width // col_width
        modelstr = '\n'.join(
                ''.join(s.ljust(col_width) for s in b).strip()
            for b in batched(symbols, max(cols, 1)))
    else:
        modelstr = "<empty>"
    return modelstr


@test
def format_symbols_basic():
    test.eq('a', format_symbols(['a']))
    test.eq('a  b  c  d', format_symbols(['a', 'b', 'c', 'd']))
    test.eq('a  b  c  d', format_symbols([' a  ', '\tb', '\nc\n', '  d '])) # strip
    with mock.patch("shutil.get_terminal_size", lambda _: (10,20)):
        test.eq('a  b  c\nd', format_symbols(['a', 'b', 'c', 'd']))
    with mock.patch("shutil.get_terminal_size", lambda _: (8,20)):
        test.eq('a  b\nc  d', format_symbols(['a', 'b', 'c', 'd']))
    with mock.patch("shutil.get_terminal_size", lambda _: (4,20)):
        test.eq('a\nb\nc\nd', format_symbols(['a', 'b', 'c', 'd']))


def create_assert(*args):
    if len(args) > 1:
        args = clingo.Function('', args)
    else:
        args = args[0]
    return args, clingo.Function("assert", (args,))


@test
def create_some_asserts():
    Number = clingo.Number
    Function = clingo.Function
    test.eq((Number(3), Function('assert', [Number(3)])),
            create_assert(Number(3)))
    test.eq((Function('', [Number(4), Number(2)]), Function('assert', [Function('', [Number(4), Number(2)])])),
            create_assert(Number(4), Number(2)))


class Tester:

    def __init__(self, filename, name):
        self._filename = filename
        self._name = name
        self._asserts = {}
        self._anys = set()
        self._models_ist = 0
        self._models_soll = -1
        self._current_rule = None
        self.failures = []
        self.constraints = []
        self._symbols = {}
        self._rules = collections.defaultdict(set)


    def add_assert(self, a):
        self._asserts[a] = self._current_rule


    def all(self, *args):
        """ ASP API: add a named assert to be checked for each model """
        args, assrt = create_assert(*args)
        #if rule := self._asserts.get(assrt):
        #    if rule != self._current_rule:
        #        print(f"WARNING: duplicate assert: {assrt}, {self._current_rule}")
        self.add_assert(assrt)
        return args


    def any(self, *args):
        args, assrt = create_assert(*args)
        if assrt in self._anys:
            print(f"WARNING: duplicate assert: {assrt}")
        self._anys.add(assrt)
        return args


    def models(self, n):
        """ ASP API: add assert for the total number of models """
        self._models_soll = n.number
        return self.all(clingo.Function("models", [n]))


    def on_model(self, model):
        """ Callback when model is found; count model and check all asserts. """
        by_signature = model.context.symbolic_atoms.by_signature
        if self._models_soll == -1:
            models = next(by_signature('models', 1), None)
            if models:
                self._models_soll = models.symbol.arguments[0].number
        self._models_ist += 1

        def find_constraints(*names):
            for name in names:
                for arity in (1,2):
                    for symbolic_atom in by_signature(name, arity):
                        # TODO TEST (although I still don't know how to trigger)
                        #if symbolic_atom.is_fact: <= this is NOT the same condition as model.is_true
                        if model.is_true(symbolic_atom.literal):
                            yield symbolic_atom

        for constraint in find_constraints('none', 'cannot'):
            self.constraints.append(constraint.symbol)

        for a, s in self._symbols.items():
            body = self._rules[a]
            if s in self._asserts and len(body) > 1:
                self.failures.append(
                        Warning(f"Duplicate: {s} (disjunction found) in {self._name}."))
                return False

        #for ensure in (s for s in model.symbols(atoms=True) if has_name(s, 'ensure')):
        for a in model.context.symbolic_atoms.by_signature('ensure', 1):
            ensure = a.symbol
            fact = ensure.arguments[0]
            self.add_assert(fact)

        for a in set(self._anys):
            if model.contains(a):
                self._anys.remove(a)
        failures = [a for a in self._asserts if not model.contains(a)] + self.constraints
        if failures:
            modelstr = format_symbols(model.symbols(shown=True))
            self.failures.append(AssertionError(
                f"MODEL:\n{modelstr}\n"
                f"Failures in {self._filename}, #program {self._name}():\n"
                f"{', '.join(map(str, failures))}\n"))
            return False
        return True


    def report(self):
        """ When done, check assert(@models(n)) explicitly, then report. """
        if self.failures:
            assert len(self.failures) == 1, self.failures
            raise self.failures[0]
        models = self._models_ist
        if not self._asserts:
            return {'asserts': set(), 'models': models}
        if self._name != 'base':
            # in 'base' all asserts are for @all models and (@any is not allowed; TODO)
            # also, with 'base' we can have 0 or more models, which are not checked
            # because 'base' can be included elsewhere, and that context can influence
            # the number of models found.
            assert models > 0, f"{self._filename}: {self._name}: no models found."
            if models != self._models_soll:
                raise Exception(f"Expected {self._models_soll} models, found {models}.")
            #assert models == self._models_soll, f"Expected {self._models_soll} models, found {models}."
        assert not self._anys, f"Asserts not in any of the {models} models:{CR}{CR.join(str(a) for a in self._anys)}"
        return dict(asserts={str(a) for a in self._asserts}, models=models)


    def rule(self, choice, heads, body):
        """ Observer callback
            Needed for detecting duplicate assertions. It collects all rules and afterwards
            checks it there are rules for asserts that have multiple bodies (disjunctions).
        """
        for h in heads:
            if body:  #TODO TestMe
                self._rules[h].add(tuple(body))
        self._current_rule = choice, heads, body

    def output_atom(self, symbol, atom):
        self._symbols[atom] = symbol



class TesterHook:

    def __init__(this, on_report=print_test_result):
        this.programs = {}
        this.program_nodes = []
        this.on_report = on_report

    def parts(this):
        # TODO test sorting
        for node in sorted(this.program_nodes, key=lambda x: x.location.begin.filename):
            yield node.location.begin.filename, node.name, [(p.name, []) for p in node.parameters]

    def parse(this, self, parameters):
        self.next.parse(parameters)
        for node in parameters['ast']:
            if program := is_program(node):
                this.program_nodes.append(node)
                name, dependencies = program
                if name in this.programs and name != 'base':
                    existing = next(node for node in this.program_nodes if name in str(node))
                    raise Exception(f"Duplicate program name: {name!r} found in {node.location.begin.filename}.")
                this.programs[name] = [(d, []) for d in dependencies]
        this._parts = this.parts()


    def ground(this, self, control, parameters):
        """ Grounds and solves the *whole* program for *each* #program test_<name> found. """
        for filename, prog_name, dependencies in this._parts:
            if prog_name.startswith('test_'):  # TODO better test
                parts = (('base', ()), *prog_with_dependencies(this.programs, prog_name, dependencies))
                #parts = (*parameters.get('parts',()), *prog_with_dependencies(this.programs, prog_name, dependencies))
            elif prog_name == 'base':  # TODO better test
                parts = (('base', ()),)
            else:
                continue
            tester = Tester(filename, prog_name)
            # We want to use a fresh control, and honor the existing handlers,
            # so we derive our parameters from the existing ones, create a new
            # control and dutyfully call self.[load|ground|solve]().
            with parameters['context'].avec(tester) as testcontext:
                testparms = dict(parameters,
                                 ast=parameters['ast'][:],    # don't let it grow with each test
                                 parts=parts,
                                 context=testcontext,  #parameters['context'].avec(tester),
                                 solve_options={'on_model': tester.on_model})
                # this is a very limited way of supplying the original command line arguments to the control
                args = [a for a in testparms['arguments'] if a not in testparms['files']]
                testcontrol = clingo.Control(args, logger=self.logger, message_limit=1)
                #testcontrol.register_observer(tester)
                self.load(testcontrol, testparms)
                self.next.ground(testcontrol, testparms)
                self.solve(testcontrol, testparms)
                report = tester.report() | {'filename': filename, 'testname': prog_name}
                this.on_report(report)
        self.next.ground(control, parameters)

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


@test
def report_not_for_base_model_count():
    t = Tester('filea.lp', 'harry')
    t._asserts['an'] = 'assert'
    with test.raises(AssertionError, 'filea.lp: harry: no models found.'):
        t.report()
    t = Tester('fileb.lp', 'base')
    t._asserts['assert1'] = 'assert'
    r = t.report()
    test.eq({'asserts': {'assert1'}, 'models': 0}, r)


def gather_tests(source):
    programs = {}
    stack = []

    def log(code, msg):
        if code == clingo.MessageCode.FileIncluded:
            filename = msg.rsplit(maxsplit=1)[-1].strip()
            stack[-1]['includes'].append(filename)

    def push(filename, add_base=True):
        ast = []
        if add_base:
            # Put program base at the top, as separating the files causes this to get lost.
            pos = clingo.ast.Position(filename, 0, 0)
            base = clingo.ast.Program(clingo.ast.Location(pos, pos), 'base', [])
            ast = [base]
        p = {'filename': filename, 'includes': [], 'programs': [], 'ast': ast}
        programs[filename] = p
        stack.append(p)
        return p

    pop = stack.pop
    current_program = None

    def process_node(node):
        nonlocal current_program
        filename = node.location.begin.filename
        print(node, file=sys.stderr)
        if not stack:
            p = push(filename, add_base=False)
        else:
            p = stack[-1]
            if filename != p['filename']:
                if filename in programs:
                    pop()
                    p = stack[-1]
                else:
                    assert current_program == 'base', f"#include only supported in 'base', not in '{current_program}', in {p['filename']}."
                    p['includes'].append(filename)
                    p = push(filename)
        assert p['filename'] == filename
        p['ast'].append(node)
        if program := is_program(node):
            name, dependencies = program
            current_program = name
            if name != 'base':
                p['programs'].append(program)

    clingo.ast.parse_files(
            [source],
            callback=process_node,
            logger=log)

    return programs


@test
def run_unit_test_separately_on_include(tmp_path):
    part_a = tmp_path/'part_a.lp'
    part_b = tmp_path/'part_b.lp'
    part_c = tmp_path/'part_c.lp'
    part_a.write_text(f'part(a).  #program test_a.  a.  cannot(fail_a).')
    part_b.write_text(f'part(b).  #include "{part_a}".  b.  #program test_b.  cannot(fail_b).')
    part_c.write_text(f'part(c).  #include "{part_b}".  c.  #include "{part_a}".  #program test_c.  cannot(fail_c).')
    tests = gather_tests(str(part_c))
    test.eq([str(part_c), str(part_b), str(part_a)], list(tests.keys()))
    program_a = tests[str(part_a)]
    program_b = tests[str(part_b)]
    program_c = tests[str(part_c)]
    test.eq(3, len(tests))

    test.eq(str(part_a), program_a['filename'])
    test.eq(str(part_b), program_b['filename'])
    test.eq(str(part_c), program_c['filename'])

    test.eq([], program_a['includes'])
    test.eq([str(part_a)], program_b['includes'])
    test.eq([str(part_b), str(part_a)], program_c['includes'])

    test.eq(['#program base.', 'part(a).', '#program test_a.', 'a.', 'cannot(fail_a).'], [str(a) for a in program_a['ast']])
    test.eq(['#program base.', 'part(b).', '#program base.', 'b.', '#program test_b.', 'cannot(fail_b).'], [str(a) for a in program_b['ast']])
    test.eq(['#program base.', 'part(c).', '#program base.', 'c.', '#program test_c.', 'cannot(fail_c).'], [str(a) for a in program_c['ast']])

    test.eq([('test_a', [])], program_a['programs'])
    test.eq([('test_b', [])], program_b['programs'])
    test.eq([('test_c', [])], program_c['programs'])


@test
def tail_includes(tmp_path):
    part_a = tmp_path/'part_a.lp'
    part_b = tmp_path/'part_b.lp'
    part_a.write_text(f'part(a).')
    part_b.write_text(f'#program test_b.  #include "{part_a}".')
    msg = f"#include only supported in 'base', not in 'test_b', in {part_b}."
    with test.raises(AssertionError, msg):
        gather_tests(str(part_b))
