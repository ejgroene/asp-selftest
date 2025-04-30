
import clingo

from .misc import Noop


def defaultcontrol_plugin(control=None, arguments=(), logger=None, message_limit=20, **etc):
    """ Creates a Control when no one else does."""

    def init(next):
        if control := next():
            return control
        return clingo.Control(arguments=arguments, logger=logger, message_limit=message_limit)

    return Noop, init, Noop, Noop, Noop

    