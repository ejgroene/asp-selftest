
""" Functions to runs all tests in an ASP program. """

import inspect
import clingo
import os
import re
import sys
import ast
import threading
import shutil
import itertools
import traceback
import importlib


from clingo import Function, Number


# Allow ASP programs started in Python to include Python themselves.
from clingo.script import enable_python
enable_python()


from .error_handling import warn2raise, AspSyntaxError


def has_name(symbol, name):
   return symbol.type == clingo.SymbolType.Function and symbol.name == name


import selftest
test = selftest.get_tester(__name__)


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


def parse_signature(s):
    """
    Parse extended #program syntax using Python's parser.
    ASP #program definitions allow a program name and simple constants are arguments:

        #program p(s1,...,sn).

    where p is the program name and arguments si are constants.

    For asp-selftest, we allow atoms as arguments:
        
        #program p(a1,...,an).

    where p is the program name and arguments ai are atoms. Atoms can be functions
    with their own arguments. This allows ai to refer to other #programs arguments.
    """
    parse = lambda o: o.value if isinstance(o, ast.Constant) else \
                   (o.id, []) if isinstance(o, ast.Name) else \
                   (o.func.id, [parse(a) for a in o.args])
    return parse(ast.parse(s).body[0].value)


# We use thread locals to communicate state between python code embedded in ASP and this module here.
local = threading.local()


def register(func):
    """ Selftest uses the context for supplying the functions @all and @models to the ASP program. 
        As a result the ASP program own Python functions are ignored. To reenable these, they must
        be registered using register(func).
    """
    assert inspect.isfunction(func), f"{func!r} must be a function"
    if tester := getattr(local, 'current_tester', None):  #TODO testme hasattr iso local.current_tester
        tester.add_function(func)


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
    test.eq((Number(3), Function('assert', [Number(3)])),
            create_assert(Number(3)))
    test.eq((Function('', [Number(4), Number(2)]), Function('assert', [Function('', [Number(4), Number(2)])])),
            create_assert(Number(4), Number(2)))


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
        self._disabled = False # because we can not remove an observer once registered
        self.failures = []


    def disable(self):
        self._disabled = True


    def add_assert(self, a):
        self._asserts[a] = self._current_rule


    def all(self, *args):
        """ ASP API: add a named assert to be checked for each model """
        args, assrt = create_assert(*args)
        if rule := self._asserts.get(assrt):
            if rule != self._current_rule:
                print(f"WARNING: duplicate assert: {assrt}")
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
        """ Observer callback """
        if not self._disabled:
            self._current_rule = choice, heads, body


    def __getattr__(self, name):
        if name in self._funcs:
            return self._funcs[name]
        #def f(*a, **k):
        #    print(f"{name}({a}, {k})")
        #return f
        raise AttributeError(name)


def read_programs(asp_code):
    """ read all the #program parts and register their dependencies """
    lines = asp_code.splitlines()
    programs = {'base': []}
    for i, line in enumerate(lines):
        if line.strip().startswith('#program'):
            name, dependencies = parse_signature(line.split('#program')[1].strip()[:-1])
            if name in programs:
                raise Exception(f"Duplicate program name: {name!r}")
            programs[name] = dependencies
            # rewrite into valid ASP (turn functions into plain terms)
            lines[i] = f"#program {name}({','.join(dep[0] for dep in dependencies)})."
    return lines, programs


def ground_exc(program, label=None, arguments=[], parts=(('base',()),),
               observer=None, context=None, extra_src=None,
               control=None,
               hooks=()):
    """ grounds an aps program turning messages/warnings into SyntaxErrors """
    lines = program.splitlines() if isinstance(program, str) else program
    errors = []

    class DefaultHook:
        def arguments(arguments, logger, message_limit):
            return arguments, logger, message_limit
        def add(control, source, parts):
            control.add(source)

    hooks = (DefaultHook,) + hooks

    def logger(code, message):
        warn2raise(lines, label, errors, code, message)
    message_limit = 1

    for h in hooks:
        if hasattr(h, 'arguments'):
            arguments, logger, message_limit = h.arguments(arguments, logger, message_limit)
    control = clingo.Control(arguments, logger=logger, message_limit=message_limit)

    if observer:
        control.register_observer(observer)

    try:
        for h in hooks:
            if hasattr(h, 'add'):
                h.add(control, '\n'.join(lines), parts)
        if extra_src:
            control.add(extra_src)
        control.ground(parts, context=context(control) if context else None)
    except BaseException as e:
        if errors:
            raise errors[0].with_traceback(None) from None
        else:
            raise
    if errors:
        raise errors[0]
    return control


def ground_and_solve(lines, on_model=None, **kws):
    control = ground_exc(lines, arguments=['0'], **kws)
    result = None
    if on_model:
        result = control.solve(on_model=on_model)
    return control, result


def prog_with_dependencies(programs, name, dependencies):
    yield name, [clingo.Number(42) for _ in dependencies]
    for dep, args in dependencies:
        assert dep in programs, f"Dependency {dep} of {name} not found."
        formal_args = programs.get(dep, [])
        formal_names = list(a[0] for a in formal_args)
        if len(args) != len(formal_names):
            raise Exception(f"Argument mismatch in {name!r} for dependency {dep!r}. Required: {formal_names}, given: {args}.")
        yield dep, [clingo.Number(a) for a in args]


def run_tests(lines, programs, base_programs=(), hooks=()):
    tests = [name for name in programs if name.startswith('test')]  or  ['base']
    for prog_name in tests:
        dependencies = programs[prog_name]
        to_ground = list(prog_with_dependencies(programs, prog_name, dependencies))
        to_ground.extend((b, []) for b in base_programs)  #TODO test me
        try:
            tester = local.current_tester = Tester(prog_name)
            control, result = ground_and_solve(lines,
                                               parts=to_ground,
                                               observer=tester,
                                               context=lambda _: tester,
                                               on_model=tester.on_model,
                                               hooks=hooks)
            yield prog_name, tester.report()
        except Exception as e:
            e.add_note(f"Error while running:  {prog_name}.")
            raise e from None


def parse_and_run_tests(asp_code, base_programs=(), hooks=()):
    def lookup_hook(h):
        module_name, callable_name = h.split(':')
        module = importlib.import_module(module_name)
        return getattr(module, callable_name)
    lines, programs = read_programs(asp_code)
    return run_tests(lines, programs, base_programs, hooks=tuple(lookup_hook(h) for h in hooks))


def print_test_result(name, result):
    asserts = result['asserts']
    models = result['models']
    print(f"ASPUNIT: {name}: ", end='', flush=True)
    print(f" {len(asserts)} asserts,  {models} model{'s' if models>1 else ''}")


def run_asp_tests(*files, base_programs=(), hooks=()):
    for program_file in files:
        name = getattr(program_file, 'name', str(program_file))
        print(f"Reading {name}.", flush=True)
        asp_code = program_file.read()
        for name, result in parse_and_run_tests(asp_code, base_programs, hooks=hooks):
            print_test_result(name, result)



@test
def parse_some_signatures():
    test.eq(('one', []), parse_signature("one"))
    test.eq(('one', [('two', []), ('three', [])]), parse_signature("one(two, three)"))
    test.eq(('one', [('two', []), ('three', [])]), parse_signature("one(two, three)"))
    test.eq(('one', [2, 3]), parse_signature("one(2, 3)"))
    test.eq(('one', [('two', [2, ('aap', [])]), ('three', [42])]), parse_signature("one(two(2, aap), three(42))"))


@test
def read_no_programs():
    lines, programs = read_programs(""" fact. """)
    test.eq([" fact. "], lines)
    test.eq({'base': []}, programs)


@test
def read_no_args():
    lines, programs = read_programs(""" fact. \n#program a.""")
    test.eq([" fact. ", "#program a()."], lines)
    test.eq({'base': [], 'a': []}, programs)


@test
def read_one_arg():
    lines, programs = read_programs(""" fact. \n#program a. \n #program b(a). """)
    test.eq([" fact. ", "#program a().", "#program b(a)."], lines)
    test.eq({'base': [], 'a': [], 'b': [('a', [])]}, programs)


@test
def read_function_args():
    lines, programs = read_programs(""" fact. \n#program a(x). \n #program b(a(42)). """)
    test.eq([" fact. ", "#program a(x).", "#program b(a)."], lines)  # 42 removed
    test.eq({'base': [], 'a': [('x', [])], 'b': [('a', [42])]}, programs)


@test
def check_for_duplicate_test(raises:(Exception, "Duplicate program name: 'test_a'")):
    read_programs(""" #program test_a. \n #program test_a. """)


@test
def simple_program():
    t = parse_and_run_tests("""
        fact.
        #program test_fact(base).
        assert(@all("facts")) :- fact.
        assert(@models(1)).
     """)
    test.eq(('test_fact', {'asserts': {'assert("facts")', 'assert(models(1))'}, 'models': 1}), next(t))


@test
def dependencies():
    t = parse_and_run_tests("""
        base_fact.

        #program one(b).
        one_fact.

        #program test_base(base).
        assert(@all("base_facts")) :- base_fact.
        assert(@models(1)).

        #program test_one(base, one(1)).
        assert(@all("one includes base")) :- base_fact, one_fact.
        assert(@models(1)).
     """)
    test.eq(('test_base', {'asserts': {'assert("base_facts")'       , 'assert(models(1))'}, 'models': 1}), next(t))
    test.eq(('test_one' , {'asserts': {'assert("one includes base")', 'assert(models(1))'}, 'models': 1}), next(t))


@test
def pass_constant_values():
    t = parse_and_run_tests("""
        #program fact_maker(n).
        fact(n).

        #program test_fact_2(fact_maker(2)).
        assert(@all(two)) :- fact(2).
        assert(@models(1)).

        #program test_fact_4(fact_maker(4)).
        assert(@all(four)) :- fact(4).
        assert(@models(1)).
     """)
    test.eq(('test_fact_2', {'asserts': {'assert(two)', 'assert(models(1))'}, 'models': 1}), next(t))
    test.eq(('test_fact_4', {'asserts': {'assert(four)', 'assert(models(1))'}, 'models': 1}), next(t))


@test
def warn_for_disjunctions():
    t = parse_and_run_tests("""
        time(0; 1).
        #program test_base(base).
        assert(@all(time_exists)) :- time(T).
        assert(@models(1)).
     """)
    test.eq(('test_base', {'asserts': {'assert(models(1))', 'assert(time_exists)'}, 'models': 1}), next(t))


@test
def format_empty_model():
    r = parse_and_run_tests("""
        #program test_model_formatting.
        #external what.
        assert(@all(test)) :- what.
    """)
    with test.raises(AssertionError, """FAILED: assert(test)
MODEL:
<empty>"""):
        next(r)


@test
def format_model_small():
    import unittest.mock as mock
    r = parse_and_run_tests("""
        #program test_model_formatting.
        this_is_a_fact(1..2).
        #external what.
        assert(@all(test)) :- what.
    """)
    with test.raises(AssertionError, """FAILED: assert(test)
MODEL:
this_is_a_fact(1)  
this_is_a_fact(2)  """):  
        with mock.patch("shutil.get_terminal_size", lambda _: (37,20)):
            next(r)


@test
def format_model_wide():
    import unittest.mock as mock
    r = parse_and_run_tests("""
        #program test_model_formatting.
        this_is_a_fact(1..3).
        #external what.
        assert(@all(test)) :- what.
    """)
    with test.raises(AssertionError, """FAILED: assert(test)
MODEL:
this_is_a_fact(1)  this_is_a_fact(2)  
this_is_a_fact(3)  """):  
        with mock.patch("shutil.get_terminal_size", lambda _: (38,20)):
            next(r)


@test
def ground_exc_with_label():
    with test.raises(AspSyntaxError, "syntax error, unexpected <IDENTIFIER>") as e:
        ground_exc("a.\nan error", label='my code')
    test.eq("""    1 a.
    2 an error
         ^^^^^ syntax error, unexpected <IDENTIFIER>""", e.exception.text)
        


@test
def exception_in_included_file(tmp_path):
    f = tmp_path/'error.lp'
    f.write_text("error")
    old = os.environ.get('CLINGOPATH')
    try:
        os.environ['CLINGOPATH'] = tmp_path.as_posix()
        with test.raises(AspSyntaxError, 'syntax error, unexpected EOF') as e:
            ground_exc("""#include "error.lp".""", label='main.lp')
        test.eq(f.as_posix(), e.exception.filename)
        test.eq(2, e.exception.lineno)
        test.eq('    1 error\n      ^ syntax error, unexpected EOF', e.exception.text)
    finally:
        if old:  #pragma no cover
            os.environ['CLINGOPATH'] = old


@test
def ground_and_solve_basics():
    control, result = ground_and_solve(["fact."])
    test.eq([clingo.Function('fact')], [s.symbol for s in control.symbolic_atoms.by_signature('fact', 0)])

    control, result = ground_and_solve(["#program one. fect."], parts=(('one', ()),))
    test.eq([clingo.Function('fect')], [s.symbol for s in control.symbolic_atoms.by_signature('fect', 0)])

    class O:
        @classmethod
        def init_program(self, *a):
            self.a = a
    ground_and_solve(["fict."], observer=O)
    test.eq((True,), O.a)

    class C:
        @classmethod
        def __init__(clz, control):
            pass
        @classmethod
        def goal(self, *a):
            self.a = a
            return a
    ground_and_solve(['foct(@goal("g")).'], context=C)
    test.eq("(String('g'),)", str(C.a))

    done = [False]
    def on_model(m):
        test.truth(m.contains(clingo.Function('fuct')))
        done[0] = True
    ground_and_solve(['fuct.'], on_model=on_model)
    test.truth(done[0])


@test
def parse_warning_raise_error(stderr):
    with test.raises(AspSyntaxError, "syntax error, unexpected EOF") as e:
        ground_and_solve(["abc"], label='code_a')
    test.eq("'code_a'", e.exception.filename)
    test.eq(2, e.exception.lineno)
    test.eq("    1 abc\n      ^ syntax error, unexpected EOF", e.exception.text)

    with test.raises(AspSyntaxError, 'atom does not occur in any rule head:  b') as e:
        ground_and_solve(["a :- b."])
    test.eq("ASP code", e.exception.filename)
    test.eq(1, e.exception.lineno)
    test.eq("    1 a :- b.\n           ^ atom does not occur in any rule head:  b", e.exception.text)

    with test.raises(AspSyntaxError, 'operation undefined:  ("a"/2)') as e:
        ground_and_solve(['a("a"/2).'])
    test.eq("ASP code", e.exception.filename)
    test.eq(1, e.exception.lineno)
    test.eq('    1 a("a"/2).\n        ^^^^^ operation undefined:  ("a"/2)',
            e.exception.text)

    with test.raises(AspSyntaxError, "unsafe variables in:  a(A):-[#inc_base];b.") as e:
        ground_and_solve(['a(A)  :-  b.'], label='code b')
    test.eq("'code b'", e.exception.filename)
    test.eq(1, e.exception.lineno)
    test.eq("""    1 a(A)  :-  b.
        ^ 'A' is unsafe
      ^^^^^^^^^^^^ unsafe variables in:  a(A):-[#inc_base];b.""",
            e.exception.text)

    with test.raises(AspSyntaxError, "global variable in tuple of aggregate element:  X") as e:
        ground_and_solve(['a(1). sum(X) :- X = #sum { X : a(A) }.'])
    test.eq("ASP code", e.exception.filename)
    test.eq(1, e.exception.lineno)
    test.eq("""    1 a(1). sum(X) :- X = #sum { X : a(A) }.
                                 ^ global variable in tuple of aggregate element:  X""",
            e.exception.text)


@test
def unsafe_variables():
    with test.raises(AspSyntaxError, "unsafe variables in:  output(A,B):-[#inc_base];input.") as e:
        ground_exc("""
            input.
            output(A, B)  :-  input.
            % comment""")
    test.eq("ASP code", e.exception.filename)
    test.eq(3, e.exception.lineno)
    test.eq("""    1 
    2             input.
    3             output(A, B)  :-  input.
                         ^ 'A' is unsafe
                            ^ 'B' is unsafe
                  ^^^^^^^^^^^^^^^^^^^^^^^^ unsafe variables in:  output(A,B):-[#inc_base];input.
    4             % comment""", e.exception.text)


@test
def multiline_error():
    with test.raises(AspSyntaxError,
                     "unsafe variables in:  geel(R):-[#inc_base];iets_vrij(S);(S,T,N)=R;R=(S,T,N)."
                     ) as e:
        ground_exc("""
            geel(R)  :-
                iets_vrij(S), R=(S, T, N).
            %%%%""")
    test.eq("ASP code", e.exception.filename)
    test.eq(3, e.exception.lineno)
    test.eq("""    1 
    2             geel(R)  :-
                       ^ 'R' is unsafe
    3                 iets_vrij(S), R=(S, T, N).
                                          ^ 'T' is unsafe
                                             ^ 'N' is unsafe
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ unsafe variables in:  geel(R):-[#inc_base];iets_vrij(S);(S,T,N)=R;R=(S,T,N).
    4             %%%%""", e.exception.text)



@test
def ensure_iso_python_call():
    t = parse_and_run_tests('a(2).  models(1).  assert("a") :- a(42).  ensure(assert("a")).')
    try:
        next(t)
        test.fail("should raise")  # pragma no cover
    except AssertionError as e:
        test.contains(str(e), 'FAILED: assert("a")')
    t = parse_and_run_tests('a(2).  models(1).  assert("a") :- a(2).  ensure(assert("a")).')
    test.eq(('base', {'asserts': {'assert("a")'}, 'models': 1}), next(t))


@test
def alternative_models_predicate():
    t = parse_and_run_tests("""
        assert(1).
        ensure(assert(1)).
        models(1).
     """)
    test.eq(('base', {'asserts': {'assert(1)'}, 'models': 1}), next(t))


@test
def warning_about_duplicate_assert():
    t = parse_and_run_tests("""
        #program test_one.
        a(1; 2).
        assert(@all("A"))  :-  a(1).
        assert(@all("A"))  :-  a(2).
        assert(@models(1)).
     """)
    with test.stdout as o:
        next(t)
    test.contains(o.getvalue(), 'WARNING: duplicate assert: assert("A")')


@test
def NO_warning_about_duplicate_assert():
    t = parse_and_run_tests("""
        #program test_one.
        a(1; 2).
        assert(@all("A"))  :-  { a(N) } = 2.
        assert(@models(1)).
     """)
    with test.stdout as o:
        next(t)
    test.complement.contains(o.getvalue(), 'WARNING: duplicate assert: assert("A")')


@test
def do_not_report_on_base_without_any_asserts():
    t = parse_and_run_tests("some. stuff.")
    test.eq(('base', {'asserts': set(), 'models': 1}), next(t))


@test
def assert_with_any():
    t = parse_and_run_tests("""
        #program test_one.
        a; b.
        assert(@any(a))  :-  a.
        assert(@any(b))  :-  b.
        assert(@all(ab)) :- { a; b } = 1.
        assert(@models(2)).
     """)
    test.eq(('test_one', {'asserts': {'assert(ab)', 'assert(models(2))'}, 'models': 2}), next(t))


@test
def duplicate_any_warning(stdout):
    t = parse_and_run_tests("""
        #program test_one.
        a; b.
        assert(@any(a))  :-  a.
        assert(@any(a))  :-  b.
        assert(@models(2)).
     """)
    next(t)
    test.eq("WARNING: duplicate assert: assert(a)\n", stdout.getvalue())


@test
def check_args_of_dependencies():
    t = parse_and_run_tests("""
        #program a(x).
        #program test_b(a).
        b.
    """)
    with test.raises(
            Exception,
            "Argument mismatch in 'test_b' for dependency 'a'. Required: ['x'], given: []."):
        next(t)


@test
def hook_basics():
    with test.raises(SyntaxError, 'atom does not occur in any rule head:  b'):
        ground_exc("""a :- b.""")
    class test_hook:
        def arguments(arguments, logger, message_limit):
            if not 'no-atom-undefined' in arguments:
                arguments += ['--warn', 'no-atom-undefined']
            return arguments, logger, message_limit
    ground_exc("""a :- b.""", hooks=(test_hook,))


# more tests in __init__ to avoid circular imports
