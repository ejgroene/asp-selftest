
# maybe silence tester before all else
from .arguments import maybe_silence_tester
maybe_silence_tester()


# import/run tests for arguments after --silent checked
from .arguments_tests import *


def test_hook(control):
    """ hook used for testing --processor option to main """
    control.add("""
        assert(@all(test_hook_was_here)).
        assert(@models(1)).
        """)


# reexport/publish some stuff
from .runasptests import ground_exc



# some tests here because the rely on runasptests being initialized.

from .runasptests import parse_and_run_tests

@test
def register_python_function():
    t = parse_and_run_tests("""
#script (python)
def repeat(message):
    return message
import asp_selftest
asp_selftest.register(repeat)
#end.

#program test_me(base).
assert(@all(@repeat("hi"))).
assert(@models(1)).
""")
    test.contains(next(t)[1]['asserts'], 'assert("hi")')


@test
def reraise_unknown_exceptinos():
    t = parse_and_run_tests("""
#script (python)
def exception_raiser():
    raise Exception("unknown")
import asp_selftest
asp_selftest.register(exception_raiser)
#end.

predicate(@exception_raiser()).
""")
    with test.raises(Exception, 'unknown'):
        next(t)


@test
def extra_source():
    c = ground_exc("a.", extra_src='b.')
    test.eq('a', str(next(c.symbolic_atoms.by_signature('a', 0)).symbol))
    test.eq('b', str(next(c.symbolic_atoms.by_signature('b', 0)).symbol))

