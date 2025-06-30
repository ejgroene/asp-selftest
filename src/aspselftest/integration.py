

""" Integration tests """


import clingo
import contextlib
import sys

from .plugins.misc import write_file

from clingo.script import enable_python
enable_python()


from .session2 import session2
from .plugins import (
    source_plugin,
    clingo_control_plugin,
    clingo_sequencer_plugin,
    insert_plugin_plugin,
    clingo_defaults_plugin)

import selftest
test = selftest.get_tester(__name__)


@test
def without_session_no_problem_with_control():
    def control_plugin(next, source):
        control = clingo.Control()
        def main():
            control.add(source)
            control.ground()
            return control.solve(yield_=True)
        return main
    response = control_plugin(None, source="a. b. c.")
    # reponse saves the control from the GC iff we keep it in a local
    # because the control is in the free variables of response
    test.eq(('control', 'source'), response.__code__.co_freevars)
    # so we call it now, and not in one line as in control_plugin(..)()
    result = response()
    models = 0
    with result:
        for model in result:
            models += 1
            test.eq('a b c', str(model))
    test.eq(1, models)


@test
def maybe_session_is_the_problem():
    def control_plugin(next, source):
        control = clingo.Control()
        def main():
            control.add(source)
            control.ground()
            # we cannot use the trick from previous test because session2() already
            # calls the plugin for us and we loose the control
            # therefor we keep it save on the handle
            # See also clingo_defaults_plugin.
            handle = control.solve(yield_=True)
            handle.__control = control  # save control from GC
            return handle
        return main
    result = session2(plugins=(control_plugin,), source="a. b. c.")  
    models = 0
    with result:
        i = iter(result)
        m = i.__next__()
        models += 1
        m = str(m)
        test.eq('a b c', m)
    test.eq(1, models)


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


    @contextlib.contextmanager
    def avec(self, context):
        self._contexts.append(context)
        """ functional style new CompoundContext with one extra context """
        yield self #CompoundContext(*self._contexts, context)
        del self._contexts[-1]


def clingo_compoundcontext_plugin(next, **etc):
    logger, load, _ground, solve = next(**etc)
    def ground(control, parts=(('base', ()),), context=None):
        compound_context = CompoundContext()
        if context:
            compound_context.add_context(context)
        _ground(control, parts=parts, context=compound_context)
    return logger, load, ground, solve
    
    
class ContextA:
    def a(self):
        return clingo.String("AA")
    
def context_a_plugin(next, **etc):
    logger, load, _ground, solve = next(**etc)
    def ground(control, parts, context):
        context.add_context(ContextA())
        _ground(control, parts=parts, context=context)
    return logger, load, ground, solve

    
@test
def use_multiple_contexts():
    class ContextB:
        def b(self):
            return clingo.String("BB")

    aspcode = f"""\
insert_plugin("{__name__}:{context_a_plugin.__qualname__}").
#script (python)
import clingo
def c():
    return clingo.String("CC")
#end.
a(@a()). b(@b()). c(@c()).
"""
    result = session2(
        plugins=(
            source_plugin,
            clingo_control_plugin,
            clingo_sequencer_plugin,
            clingo_compoundcontext_plugin,
            insert_plugin_plugin,
            clingo_defaults_plugin
        ),
        source=aspcode,
        context=ContextB(),
        yield_=True)
    test.isinstance(result, clingo.SolveHandle)
    with result as h:
        test.truth(h.get().satisfiable)
        for m in h:
            test.eq("a b c d", str(m))

