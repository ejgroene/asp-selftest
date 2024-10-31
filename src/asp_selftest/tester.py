import sys
import io
import collections
import shutil
import itertools
import clingo
import threading
import inspect

import selftest
test = selftest.get_tester(__name__)


def has_name(symbol, name):
   return symbol.type == clingo.SymbolType.Function and symbol.name == name


def print_test_result(name, result):
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


def format_symbols(symbols):
    symbols = sorted(str(s) for s in symbols)
    if len(symbols) > 0:
        col_width = (max(len(w) for w in symbols)) + 2
        width, h = shutil.get_terminal_size((120, 20))
        cols = width // col_width
        modelstr = '\n'.join(
                ''.join(s.ljust(col_width) for s in b)
            for b in batched(symbols, max(cols, 1)))
    else:
        modelstr = "<empty>"
    return modelstr


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


local = threading.local()


def register(func):
    """ Selftest uses the context for supplying the functions @all and @models to the ASP program. 
        As a result the ASP program own Python functions are ignored. To reenable these, they must
        be registered using register(func).
    """
    assert inspect.isfunction(func), f"{func!r} must be a function"
    if tester := getattr(local, 'current_tester', None):  #TODO testme hasattr iso local.current_tester
        tester.add_function(func)

sys.modules['__main__'].register = register

class Tester:

    def __init__(self, name=None):
        self.reset(name)


    def reset(self, name):
        self._name = name
        self._asserts = {}
        self._anys = set()
        self._models_ist = 0
        self._models_soll = -1
        self._funcs = {}
        self._current_rule = None
        self.failures = []
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
        if self._models_soll == -1:
            models = next((s for s in model.symbols(atoms=True) if has_name(s, 'models')),
                          None)
            if models:
                self._models_soll = models.arguments[0].number
        self._models_ist += 1

        for a, s in self._symbols.items():
            body = self._rules[a]
            if s in self._asserts and len(body) > 1:
                self.failures.append(Warning(f"Duplicate: {s} (disjunction found)"))
                return False

        for ensure in (s for s in model.symbols(atoms=True) if has_name(s, 'ensure')):
            fact = ensure.arguments[0]
            self.add_assert(fact)

        for a in set(self._anys):
            if model.contains(a):
                self._anys.remove(a)
        failures = [a for a in self._asserts if not model.contains(a)]
        if failures:
            modelstr = format_symbols(model.symbols(shown=True))
            self.failures.append(AssertionError(f"FAILED: {', '.join(map(str, failures))}\nMODEL:\n{modelstr}"))
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
        assert models > 0, f"{self._name}: no models found."
        assert not self._anys, f"Asserts not in any of the {models} models:{CR}{CR.join(str(a) for a in self._anys)}"
        assert models == self._models_soll, f"Expected {self._models_soll} models, found {models}."
        return dict(asserts={str(a) for a in self._asserts}, models=models)


    def add_function(self, func):
        self._funcs[func.__name__] = func

   
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

    def __getattr__(self, name):
        if name in self._funcs:
            return self._funcs[name]
        raise AttributeError(name)



class CompoundContext:
    """ Clingo looks up functions in __main__ OR in context; we need both.
        (Functions defined in #script land in __main__)
    """

    def __init__(self, *contexts):
        self._contexts = contexts

    def add_context(self, *context):
        self._contexts += context

    def __getattr__(self, name):
        for c in self._contexts:
            if f := getattr(c, name, None):
                return f
        return getattr(sys.modules['__main__'], name)


class TesterHook:

    def __init__(this, on_report=print_test_result):
        this.programs = {}
        this.ast = []   # we keep a copy of the ast to load it for each test
        this.on_report = on_report


    def parse(this, self, ctl, files, on_ast):
        def filter(a):
            if p := is_program(a):
                name, dependencies = p
                if name in this.programs:
                    raise Exception(f"Duplicate program name: {name!r}")
                this.programs[name] = [(d, []) for d in dependencies]
            on_ast(a)
            this.ast.append(a)
        self.parse(ctl, files, filter)


    def ground(this, self, ctl, base_parts, context):
        for prog_name, dependencies in this.programs.items():
            if not(prog_name.startswith('test_') or prog_name == 'base'):
                continue
            parts = base_parts + list(prog_with_dependencies(this.programs, prog_name, dependencies))
            try:
                tester = Tester()
                # play nice with other hooks; maybe also add original arguments?
                control = clingo.Control(['0'], logger=self.logger, message_limit=self.message_limit)
                control.register_observer(tester)
                self.load(control, this.ast)
                self.ground(control, parts, context=CompoundContext(tester, context))
                self.solve(control, on_model=tester.on_model)
                this.on_report(prog_name, tester.report())
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

