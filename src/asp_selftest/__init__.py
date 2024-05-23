import selftest
test = selftest.get_tester(__name__)

from .runasptests import runasptests, register



@test
def program_with_python():
    """ test import of 'register'; here because runasptests modules must have finished importing """
    from .runasptests import parse_and_run_tests
    t = parse_and_run_tests("""
#script (python)
import clingo
import asp_selftest
def f():
    return clingo.String("aap")
asp_selftest.register(f)
#end.

fact(@f()).
#program test_call_registered_python_function(base).
assert(@all("call @-function")) :- fact("aap").
assert(@models(1)).
     """)
    test.eq(('test_call_registered_python_function', {'asserts': {'assert("call @-function")', 'assert(models(1))'}, 'models': 1}), next(t))
