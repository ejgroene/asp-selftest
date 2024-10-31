
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
import collections
import tempfile


from clingo import Function, Number


# Allow ASP programs started in Python to include Python themselves.
from clingo.script import enable_python
enable_python()


from .error_handling import warn2raise, AspSyntaxError
from .application import MainApp
from .processors import SyntaxErrors
from .tester import TesterHook, CompoundContext


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



default = lambda p: tuple(p) == (('base', ()), )


def ground_exc(program, label='ASP-code', arguments=[], parts=(('base', ()),),
               observer=None, context=None, extra_src=None,
               control=None,
               hooks=()):
    """ grounds an aps program turning messages/warnings into SyntaxErrors """
    class Haak:
        def ground(this, self, ctl, x_parts, x_context):
            assert default(parts) or default(x_parts), [parts, x_parts]
            if isinstance(x_context, CompoundContext):
                x_context.add_context(context)
            self.ground(ctl,
                        x_parts if default(parts) else parts,
                        x_context or context)
    with tempfile.NamedTemporaryFile(mode='w', suffix=f"-{label}.lp") as f:
        f.write(program if isinstance(program, str) else '\n'.join(program))
        f.seek(0)
        with MainApp(hooks=list(hooks) + [SyntaxErrors(), Haak()]) as app:
            ctl = clingo.Control(arguments, logger=app.logger, message_limit=app.message_limit)
            if observer:
                ctl.register_observer(observer)
            app.main(ctl, [f.name])

    return ctl


def ground_and_solve(lines, on_model=None, **kws):
    control = ground_exc(lines, arguments=['0'], **kws)
    result = None
    if on_model:
        result = control.solve(on_model=on_model)
    return control, result


# keep
def prog_with_dependencies(programs, name, dependencies):
    yield name, [clingo.Number(42) for _ in dependencies]
    for dep, args in dependencies:
        assert dep in programs, f"Dependency {dep} of {name} not found."
        formal_args = programs.get(dep, [])
        formal_names = list(a[0] for a in formal_args)
        if len(args) != len(formal_names):
            raise Exception(f"Argument mismatch in {name!r} for dependency {dep!r}. Required: {formal_names}, given: {args}.")
        yield dep, [clingo.Number(a) for a in args]


def parse_and_run_tests(asp_code): #, base_programs=()):
    reports = []
    ctl = ground_exc(asp_code, hooks=[TesterHook(on_report=lambda *a: reports.append(a))])
    for r in reports:
        yield r

    def lookup_hook(h):
        module_name, callable_name = h.split(':')
        module = importlib.import_module(module_name)
        return getattr(module, callable_name)
    #lines, programs = read_programs(asp_code)
    #return run_tests(lines, programs, base_programs, hooks=tuple(lookup_hook(h) for h in hooks))
    return


#keep
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



#@test
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


#@test
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


#@test
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


#@test
def warn_for_disjunctions():
    t = parse_and_run_tests("""
        time(0; 1).
        #program test_base(base).
        assert(@all(time_exists)) :- time(T).
        assert(@models(1)).
     """)
    test.eq(('test_base', {'asserts': {'assert(models(1))', 'assert(time_exists)'}, 'models': 1}), next(t))


#@test
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


#@test
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


#@test
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
    test.endswith(e.exception.filename, '-code_a.lp')
    test.eq(2, e.exception.lineno)
    test.eq("    1 abc\n      ^ syntax error, unexpected EOF", e.exception.text)

    with test.raises(AspSyntaxError, 'atom does not occur in any rule head:  b') as e:
        ground_and_solve(["a :- b."])
    test.endswith(e.exception.filename, '-ASP-code.lp')
    test.eq(1, e.exception.lineno)
    test.eq("    1 a :- b.\n           ^ atom does not occur in any rule head:  b", e.exception.text)

    with test.raises(AspSyntaxError, 'operation undefined:  ("a"/2)') as e:
        ground_and_solve(['a("a"/2).'])
    test.endswith(e.exception.filename, '-ASP-code.lp')
    test.eq(1, e.exception.lineno)
    test.eq('    1 a("a"/2).\n        ^^^^^ operation undefined:  ("a"/2)',
            e.exception.text)

    with test.raises(AspSyntaxError, "unsafe variables in:  a(A):-[#inc_base];b.") as e:
        ground_and_solve(['a(A)  :-  b.'], label='code b')
    test.endswith(e.exception.filename, '-code b.lp')
    test.eq(1, e.exception.lineno)
    test.eq("""    1 a(A)  :-  b.
        ^ 'A' is unsafe
      ^^^^^^^^^^^^ unsafe variables in:  a(A):-[#inc_base];b.""",
            e.exception.text)

    with test.raises(AspSyntaxError, "global variable in tuple of aggregate element:  X") as e:
        ground_and_solve(['a(1). sum(X) :- X = #sum { X : a(A) }.'])
    test.endswith(e.exception.filename, '-ASP-code.lp')
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
    test.endswith(e.exception.filename, '-ASP-code.lp')
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
    test.endswith(e.exception.filename, '-ASP-code.lp')
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
def tester_basics():
    t = parse_and_run_tests("""
    a.
    #program test_one(base).
    assert(@all("one test")) :- a.
    assert(@models(1)).
    """)
    next(t)

#@test
def ensure_iso_python_call():
    t = parse_and_run_tests('a(2).  models(1).  assert("a") :- a(42).  ensure(assert("a")).')
    try:
        next(t)
        test.fail("should raise")  # pragma no cover
    except AssertionError as e:
        test.contains(str(e), 'FAILED: assert("a")')
    t = parse_and_run_tests('a(2).  models(1).  assert("a") :- a(2).  ensure(assert("a")).')
    test.eq(('base', {'asserts': {'assert("a")'}, 'models': 1}), next(t))


#@test
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
        #defined a/1. %a(1; 2).
        #external a(1; 2).
        assert(@all("A"))  :-  a(1).
        assert(@all("A"))  :-  a(2).
        assert(@models(1)).
     """)
    with test.raises(Warning, 'Duplicate: assert("A") (disjunction found)'):
        next(t)


@test
def NO_warning_about_duplicate_assert_1():
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
def NO_warning_about_duplicate_assert_2():
    t = parse_and_run_tests("""
        #program test_one_1.
        #defined output/3.
        time(0).
        #external bool(T, B)  :  time(T),  def_precondition(_, _, B).
        precondition(T, W, F) :- time(T), def_precondition(W, F, _),  bool(T, B) : def_precondition(W, F, B).
        def_precondition(144, voeding, "STROOM-OK").
        def_precondition(144, voeding, "SPANNING-OK").
        bool(0, "STROOM-OK").
        assert(@all("precondition"))  :-  { precondition(0, 144, voeding) } = 0.
        assert(@models(1)).
     """)
    test.eq([('test_one_1', {'asserts': {'assert("precondition")', 'assert(models(1))'}, 'models': 1})], list(t))


@test
def do_not_report_on_base_without_any_asserts():
    t = parse_and_run_tests("some. stuff.")
    #test.eq(('base', {'asserts': set(), 'models': 1}), next(t))
    test.eq([], list(t))


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

# more tests in moretests.py to avoid circular imports
