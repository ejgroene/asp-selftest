import traceback

import selftest
test =  selftest.get_tester(__name__)

from .messageparser import warn2raise
from .misc import Noop



def syntaxerror_plugin(logger=None, plugins=(), label='?', **etc):

    _errors = []

    def my_logger(next, code, message):
        error = warn2raise(None, label, code, message)
        _errors.append(error)

    def _raise():
        raise _errors[-1]

    def load(next, control, source, files):
        try:
            next(control, source, files)
        except RuntimeError as e:
            assert str(e) == "syntax error", e
            assert _errors, _errors
            _raise()

    def ground(next, control):
        next(control)
        if _errors:
            _raise()

    return my_logger, Noop, load, ground, Noop

