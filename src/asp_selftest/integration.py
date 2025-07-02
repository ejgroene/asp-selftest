

""" Integration tests """


import clingo
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
    clingo_defaults_plugin,
    stdin_to_tempfile_plugin,
    compound_context_plugin,
)

import selftest
test = selftest.get_tester(__name__)


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
            stdin_to_tempfile_plugin,
            clingo_control_plugin,
            clingo_sequencer_plugin,
            compound_context_plugin,
            insert_plugin_plugin,
            clingo_defaults_plugin
        ),
        source=aspcode,
        context=ContextB(),
        yield_=True)
    test.isinstance(result, clingo.SolveHandle)
    models = 0
    print("CONTROL:", result.__control)
    test.eq(
        ['a("AA")', 'b("BB")', 'c("CC")', 'insert_plugin("asp_selftest.integration:context_a_plugin")'],
        [str(a.symbol) for a in result.__control.symbolic_atoms])
    with result as h:
        ###
        ###  get(), resume(), model() etc FUCK UP THE HANDLE !!!!
        ###  They discard the last model and start solving the next one.
        ###  After those call, iteration is BROKEN
        ###
        for m in h:
            models += 1
            test.eq('a("AA") b("BB") c("CC") insert_plugin("asp_selftest.integration:context_a_plugin")', str(m))
    test.eq(1, models)


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


