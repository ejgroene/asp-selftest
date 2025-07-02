import sys

import selftest
test = selftest.get_tester(__name__)


class CompoundContext:
    """ Clingo looks up functions in __main__ OR in context; we need both.
        (Functions defined in #script land in __main__)
    """

    def __init__(self, *contexts):
        self._contexts = list(contexts)


    def add_context(self, *context):
        self._contexts += context
        return self


    def __getattr__(self, name):
        for c in self._contexts:
            if f := getattr(c, name, None):
                return f
        return getattr(sys.modules['__main__'], name)


def compound_context_plugin(next, **etc):

    logger, load, _ground, solve = next(**etc)

    def ground(control, parts=(('base', ()),), context=None):
        compound_context = CompoundContext()
        if context:
            compound_context.add_context(context)
        _ground(control, parts=parts, context=compound_context)

    return logger, load, ground, solve
    
    
# tests in integration.py
