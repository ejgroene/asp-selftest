
""" Functions to runs all tests in an ASP program. """

import clingo
import os
import shutil
import tempfile

from clingo import Function, Number

from .error_handling import AspSyntaxError
from .application import MainApp
from .processors import SyntaxErrors
from .tester import TesterHook
from .session import CompoundContext

import selftest
test = selftest.get_tester(__name__)


default = lambda p: tuple(p) == (('base', ()), )


def ground_exc(program, label='ASP-code', arguments=[], parts=(('base', ()),),
               observer=None, context=None, extra_src=None,
               control=None, trace=None,
               hooks=()):
    """ grounds an aps program turning messages/warnings into SyntaxErrors
        it also solves; the function name is legacy
    """
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
        with MainApp(trace=trace,
                     hooks=list(hooks) + [SyntaxErrors(), Haak()],
                     arguments=arguments) as app:
            ctl = clingo.Control(arguments, logger=app.logger, message_limit=app.message_limit)
            if extra_src:
                ctl.add(extra_src)
            if observer:
                ctl.register_observer(observer)
            app.main(ctl, [f.name])

    return ctl


def ground_and_solve(lines, on_model=None, **kws):
    control = ground_exc(lines, arguments=['0'], **kws)   # TODO this already solves
    result = None
    if on_model:
        result = control.solve(on_model=on_model)
    return control, result


def parse_and_run_tests(asp_code, base_programs=(), hooks=()):
    reports = []
    ctl = ground_exc(asp_code,
                     hooks=list(hooks) + [TesterHook(on_report=lambda r: reports.append(r))],
                     arguments=['0'])
    for r in reports:
        yield r


@test
def check_for_duplicate_test(raises:(Exception, "Duplicate program name: 'test_a'")):
    next(parse_and_run_tests(""" #program test_a. \n #program test_a. """))


@test
def simple_program():
    t = parse_and_run_tests("""
        fact.
        #program test_fact(base).
        assert(@all("facts")) :- fact.
        assert(@models(1)).
     """)
    data = next(t)
    test.endswith(data.pop('filename'), '-ASP-code.lp')
    test.eq({'testname': 'base', 'asserts': set(), 'models': 1}, data)
    data = next(t)
    test.endswith(data.pop('filename'), '-ASP-code.lp')
    test.eq({'testname': 'test_fact', 'asserts': {'assert("facts")', 'assert(models(1))'}, 'models': 1}, data)


@test
def dependencies():
    t = parse_and_run_tests("""
        base_fact.

        #program one().
        one_fact.

        #program test_base(base).
        assert(@all("base_facts")) :- base_fact.
        assert(@models(1)).

        #program test_one(base, one).
        assert(@all("one includes base")) :- base_fact, one_fact.
        assert(@models(1)).
     """)
    data = next(t)
    test.endswith(data.pop('filename'), '-ASP-code.lp')
    test.eq({'testname': 'base', 'asserts': set(), 'models': 1}, data)
    data = next(t)
    test.endswith(data.pop('filename'), '-ASP-code.lp')
    test.eq({'testname': 'test_base', 'asserts': {'assert("base_facts")', 'assert(models(1))'}, 'models': 1}, data)
    data = next(t)
    test.endswith(data.pop('filename'), '-ASP-code.lp')
    test.eq({'testname': 'test_one' , 'asserts': {'assert("one includes base")', 'assert(models(1))'}, 'models': 1}, data)


#@test   # passing parameters to programs is no longer supported
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
    data = next(t)
    test.endswith(data.pop('filename'), '-ASP-code.lp')
    test.eq({'testname': 'base', 'asserts': set(), 'models': 1}, data)
    data = next(t)
    test.endswith(data.pop('filename'), '-ASP-code.lp')
    test.eq({'testname': 'test_base', 'asserts': {'assert(models(1))', 'assert(time_exists)'}, 'models': 1}, data)


@test
def format_empty_model():
    r = parse_and_run_tests("""
        #program test_model_formatting.
        #external what.
        assert(@all(test)) :- what.
    """)
    with test.raises(AssertionError) as e:
        next(r)
    p = tempfile.gettempdir()
    msg = str(e.exception)
    test.startswith(msg, f"""MODEL:
<empty>
Failures in {p}""")
    test.endswith(msg, """, #program test_model_formatting():
assert(test)
""")


@test
def format_model_small():
    import unittest.mock as mock
    r = parse_and_run_tests("""
        #program test_model_formatting.
        this_is_a_fact(1..2).
        #external what.
        assert(@all(test)) :- what.
    """)
    with test.raises(AssertionError) as e:  
        with mock.patch("shutil.get_terminal_size", lambda _: (37,20)):
            next(r)
    msg = str(e.exception)
    p = tempfile.gettempdir()
    test.startswith(msg, f"""MODEL:
this_is_a_fact(1)
this_is_a_fact(2)
Failures in {p}""")
    test.endswith(msg, f""", #program test_model_formatting():
assert(test)
""")


@test
def format_model_wide():
    import unittest.mock as mock
    r = parse_and_run_tests("""
        #program test_model_formatting.
        this_is_a_fact(1..3).
        #external what.
        assert(@all(test)) :- what.
    """)
    with test.raises(AssertionError) as e:  
        with mock.patch("shutil.get_terminal_size", lambda _: (38,20)):
            next(r)
    msg = str(e.exception)
    p = tempfile.gettempdir()
    test.startswith(msg, f"""MODEL:
this_is_a_fact(1)  this_is_a_fact(2)
this_is_a_fact(3)
Failures in {p}""")
    test.endswith(msg, f""", #program test_model_formatting():
assert(test)
""")


@test
def tester_basics():
    t = parse_and_run_tests("""
    a.
    #program test_one(base).
    assert(@all("one test")) :- a.
    assert(@models(1)).
    """)
    next(t)

@test
def ensure_iso_python_call():
    t = parse_and_run_tests('a(2).  models(1).  assert("a") :- a(42).  ensure(assert("a")).')
    try:
        next(t)
        test.fail("should raise")  # pragma no cover
    except AssertionError as e:
        test.contains(str(e), 'Failures in ')
        test.contains(str(e), '#program base():\nassert("a")\n')
    t = parse_and_run_tests('a(2).  models(1).  assert("a") :- a(2).  ensure(assert("a")).')
    data = next(t)
    test.endswith(data.pop('filename'), '-ASP-code.lp')
    test.eq({'testname': 'base', 'asserts': {'assert("a")'}, 'models': 1}, data)


@test
def alternative_models_predicate():
    t = parse_and_run_tests("""
        assert(1).
        ensure(assert(1)).
        models(1).
     """)
    data = next(t)
    test.endswith(data.pop('filename'), '-ASP-code.lp')
    test.eq({'testname': 'base', 'asserts': {'assert(1)'}, 'models': 1}, data)


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
    with test.raises(Warning) as e:
        next(t)
    msg = str(e.exception)
    test.startswith(msg,
        'Duplicate: assert("A") (disjunction found) in test_one in /')
    test.endswith(msg,
        '-ASP-code.lp.')


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
    data = next(t)
    data.pop('filename')
    test.eq({'testname': 'base', 'asserts': set(), 'models': 1}, data)
    data = next(t)
    data.pop('filename')
    test.eq({'testname': 'test_one_1', 'asserts': {'assert("precondition")', 'assert(models(1))'}, 'models': 1}, data)
    test.eq([], list(t))


@test
def do_not_report_on_base_without_any_asserts():
    t = parse_and_run_tests("some. stuff.")
    data = next(t)
    data.pop('filename')
    test.eq({'testname': 'base', 'asserts': set(), 'models': 1}, data)
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
    data = next(t)
    data.pop('filename')
    test.eq({'testname': 'base', 'asserts': set(), 'models': 1}, data)
    data = next(t)
    data.pop('filename')
    test.eq({'testname': 'test_one', 'asserts': {'assert(ab)', 'assert(models(2))'}, 'models': 2}, data)


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
    test.endswith(stdout.getvalue(), "WARNING: duplicate assert: assert(a)\n")


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
def constraints_are_more_better(stdout):
    # The idea is to writes asserts just like ASP constraints, but by providing a head (which in an 
    # ASP constraint can never be true) we catch the result, and if it is true, we raise AssertionError.
    # So the constraint does not work as a contraint in the sense that it limit the possible models, it
    # only signals the models that are not correct; if there are any. We use 'none' as the predicate
    # as to indicate that not a single model containing this constraint is valid.
    t = parse_and_run_tests("""
        #program test_constraints.
        a.
        none("not in a single model")  :-  a.
    """)
    with test.raises(AssertionError) as e:
        next(t)
    test.startswith(str(e.exception), """MODEL:
a                              none("not in a single model")
Failures in """)
    test.endswith(str(e.exception), '#program test_constraints():\nnone("not in a single model")\n')


# more tests in moretests.py to avoid circular imports
