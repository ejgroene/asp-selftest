

""" Integration tests """


import sys
import os

import clingo

from .plugins.misc import write_file, list_symbols

from .session2 import session2, clingo_session

from .plugins import (
    source_plugin,
    clingo_control_plugin,
    clingo_sequencer_plugin,
    insert_plugin_plugin,
    clingo_defaults_plugin,
    clingo_syntaxerror_plugin,
    testrunner_plugin,
    stdin_to_tempfile_plugin,
    compound_context_plugin,
    clingo_reify_plugin,
)

import selftest
test = selftest.get_tester(__name__)


def ground_exc(source=None, label=None, files=(),
               include_paths=(), arguments=(),
               observer=None, trace=None,
               session=clingo_session,
               **etc):
    """ a general pupose one-stop ground function """
    old_path = os.environ.get('CLINGOPATH', '').split(':')
    os.environ['CLINGOPATH'] = ':'.join((*old_path, *include_paths))
    try:
        control = clingo.Control(arguments=arguments)
        if observer:
            control.register_observer(observer)
        session(
            control=control,
            source=source,
            label=label,
            files=files,
            arguments=arguments,
            yield_=True,
            **etc) # not consuming the result so no solving takes place
        return control
    finally:
        os.environ.pop('CLINGOPATH')
        if old_path:
            os.environ['CLINGOPATH'] = ':'.join(old_path)


@test
def ground_simple(stdout):
    control = ground_exc(source="a. b.")
    test.isinstance(control, clingo.Control)
    test.eq(['a', 'b'], list_symbols(control))
    test.endswith(stdout.getvalue(), "-string.lp\nTesting base\n  base\n")


@test
def ground_files(tmp_path, stdout):
    f1 = write_file(tmp_path/'f1', "f(1).")
    f2 = write_file(tmp_path/'f2', "f(2).")
    control = ground_exc(files=(f1, f2))
    test.eq(['f(1)', 'f(2)'], list_symbols(control))
    out = stdout.getvalue()
    test.contains(out, "/f1\nTesting ")
    test.contains(out, "/f2\nTesting base\n  base\n")


@test
def ground_with_observer(stdout):
    atoms = {}
    class MyObserver:
        def output_atom(self, symbol, atom):
            atoms[atom] = symbol
    ground_exc(source="a.", observer=MyObserver())
    test.eq({0: clingo.Function('a', [], True)}, atoms)
    test.endswith(stdout.getvalue(), "-string.lp\nTesting base\n  base\n")


@test
def pass_arguments_to_control(stdout):
    with test.raises(SyntaxError, "atom does not occur in any rule head:  b"), test.stderr as stderr:
        ground_exc(source="a :- b.")
    test.endswith(stderr.getvalue(), "-string.lp:1:6-7: info: atom does not occur in any rule head:\n  b\n\n")
    c = ground_exc(source="c. a :- b.", arguments=['--warn', 'no-atom-undefined'])
    test.eq(['c'], list_symbols(c))
    test.eq(2, stdout.getvalue().count("-string.lp\nTesting base\n  base\n"))


@test
def raise_syntaxerror():
    with test.raises(SyntaxError, "syntax error, unexpected EOF") as e:
        ground_exc(source="foutje")
    test.eq('    1 foutje\n      ^ syntax error, unexpected EOF', e.text)


@test
def has_reify(stdout):
    c = ground_exc(source="b. rule(a, b).")
    test.eq(['b', 'a', 'rule(a,b)'], list_symbols(c))
    test.endswith(stdout.getvalue(), "-string.lp\nTesting base\n  base\n")


@test
def include_path(tmp_path, stdout):
    before = os.environ.get('CLINGOPATH', 'nope')
    (tmp_path/'inc.lp').write_text("included.")
    c = ground_exc(source='#include "inc.lp".', include_paths=[tmp_path.as_posix()])
    test.eq(['included'], list_symbols(c))
    after = os.environ.get('CLINGOPATH', 'nope')
    test.eq(before, after)
    out = stdout.getvalue()
    test.contains(out, "/inc.lp\nTesting ")
    test.endswith(out, "-string.lp\nTesting base\n  base\n")


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
            stdin_to_tempfile_plugin,
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


