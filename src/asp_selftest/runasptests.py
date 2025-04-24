
""" Functions to runs all tests in an ASP program. """

import clingo
import os
import shutil
import tempfile

from clingo import Function, Number

from .tester import TesterHook
from .syntaxerrorhandler import AspSyntaxError, ground_exc


import selftest
test = selftest.get_tester(__name__)


default = lambda p: tuple(p) == (('base', ()), )



def parse_and_run_tests(asp_code, base_programs=(), hooks=()):
    reports = []
    ctl = ground_exc(asp_code,
                     handlers=hooks + (TesterHook(on_report=lambda r: reports.append(r)),),
                     arguments=['0'])
    for r in reports:
        yield r


@test
def check_for_duplicate_test(raises:(Exception, "Duplicate test: 'test_a' found in <string>.")):
    next(parse_and_run_tests(""" #program test_a. \n #program test_a. """))


@test
def simple_program():
    t = parse_and_run_tests("""
        fact.
        #program test_fact(base).
        cannot("facts") :- not fact.
        models(1).
     """)
    data = next(t)
    test.endswith(data.pop('filename'), '<string>')
    test.eq({'testname': 'test_fact', 'models': 1}, data)


@test
def dependencies():
    t = parse_and_run_tests("""
        base_fact.

        #program one().
        one_fact.

        #program test_base(base).
        cannot("base_facts") :- not base_fact.
        models(1).

        #program test_one(base, one).
        cannot("one includes base") :- base_fact, not one_fact.
        models(1).
     """)
    #data = next(t)
    #test.endswith(data.pop('filename'), '<string>')
    #test.eq({'testname': 'base', 'asserts': set(), 'models': 1}, data)
    data = next(t)
    test.endswith(data.pop('filename'), '<string>')
    test.eq({'testname': 'test_base', 'models': 1}, data)
    data = next(t)
    test.endswith(data.pop('filename'), '<string>')
    test.eq({'testname': 'test_one' , 'models': 1}, data)


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
def format_empty_model():
    r = parse_and_run_tests("""
        #program test_model_formatting.
        #external what.
        cannot(test) :- not what.
    """)
    with test.raises(AssertionError) as e:
        next(r)
    p = tempfile.gettempdir()
    msg = str(e.exception)
    test.eq(msg, f"""MODEL:
<empty>
Failures in <string>, #program test_model_formatting():
cannot(test)
""")


@test
def format_model_small():
    import unittest.mock as mock
    r = parse_and_run_tests("""
        #program test_model_formatting.
        this_is_a_fact(1..2).
        #external what.
        cannot(test) :- not what.
    """)
    with test.raises(AssertionError) as e:  
        with mock.patch("shutil.get_terminal_size", lambda _: (37,20)):
            next(r)
    msg = str(e.exception)
    p = tempfile.gettempdir()
    test.startswith(msg, f"""MODEL:
this_is_a_fact(1)
this_is_a_fact(2)
Failures in <string>, #program test_model_formatting():
cannot(test)
""")


@test
def format_model_wide():
    import unittest.mock as mock
    r = parse_and_run_tests("""
        #program test_model_formatting.
        this_is_a_fact(1..3).
        #external what.
        cannot(test) :- not what.
    """)
    with test.raises(AssertionError) as e:  
        with mock.patch("shutil.get_terminal_size", lambda _: (38,20)):
            next(r)
    msg = str(e.exception)
    p = tempfile.gettempdir()
    test.startswith(msg, f"""MODEL:
this_is_a_fact(1)  this_is_a_fact(2)
this_is_a_fact(3)
Failures in <string>, #program test_model_formatting():
cannot(test)
""")


@test
def tester_basics():
    t = parse_and_run_tests("""
    a.
    #program test_one(base).
    cannot("one test") :- not a.
    models(1).
    """)
    next(t)


@test
def alternative_models_predicate():
    t = parse_and_run_tests("""
        #program test_x.
        models(1).
     """)
    data = next(t)
    test.endswith(data.pop('filename'), '<string>')
    test.eq({'testname': 'test_x', 'models': 1}, data)


#@test  this check is about to disappear because of none/cannot
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
    test.eq(msg,
        'Duplicate: assert("A") (disjunction found) in test_one in <string>.')


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
        b(1).
        cannot("not in any model")  :-  a.                %fails
        constraint("not in any model", B)  :-  b(B).      %fails
    """)
    with test.raises(AssertionError) as e:
        next(t)
    test.eq("""MODEL:
a     b(1)
Failures in <string>, #program test_constraints():
constraint("not in any model",1), cannot("not in any model")
""",
            str(e.exception), diff=test.diff)


# more tests in moretests.py to avoid circular imports
