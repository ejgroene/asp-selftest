
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

