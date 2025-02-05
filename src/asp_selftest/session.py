
import sys
import contextlib
import importlib

import clingo.ast

from .delegate import Delegate
from .utils import find_symbol, is_processor_predicate

import selftest
test = selftest.get_tester(__name__)


class CompoundContext:
    """ Clingo looks up functions in __main__ OR in context; we need both.
        (Functions defined in #script land in __main__)
    """

    def __init__(self, *contexts):
        self._contexts = contexts

    def add_context(self, *context):
        self._contexts += context

    def __getattr__(self, name):
        for c in self._contexts:
            if f := getattr(c, name, None):
                return f
        return getattr(sys.modules['__main__'], name)



class DefaultHandler:
    """ implements all basic operations on Clingo, meant as last handler """

    def parse(this, self, parameters):
        """ parse code in source or files into an ast, scans for
            processor directives and adds processors on the fly."""
        parameters['ast'] = []
        append = parameters['ast'].append
        def add(node):
            if processor_name := is_processor_predicate(node):
                handler = self.add_handler(processor_name)
                for method_name in ('prepare', 'parse'):
                    assert not hasattr(handler, method_name), f"{method_name!r} of {processor_name} can never be called."
            append(node)
        if 'files' in parameters:
            clingo.ast.parse_files(parameters['files'], callback=add, logger=self.logger, message_limit=1)
        if 'source' in parameters:
            clingo.ast.parse_string(parameters['source'], callback=add, logger=self.logger, message_limit=1)

    def control(this, self, parameters):
        """ if no one did something smart, we create an default control """
        return clingo.Control()

    def load(this, self, control, parameters):
        """ loads the AST into the given control """
        with clingo.ast.ProgramBuilder(control) as b:
            add = b.add
            for a in parameters['ast']:
                add(a)

    def ground(this, self, control, parameters):
        """ ground the given parts, using context """
        parameters.setdefault('parts', [('base', ()),])
        parameters.setdefault('context', CompoundContext())
        control.ground(parameters['parts'], context=parameters['context'])

    def solve(this, self, control, parameters):
        """ solves and return an iterator with models, if any """
        parameters.setdefault('solve_options', {'yield_': True})
        return control.solve(**parameters['solve_options'])

    def logger(this, self, code, message):
        """ if no one cares, we just print """
        print(message)



class AspSession(Delegate, contextlib.AbstractContextManager):
    """ More sensible interface to Clingo, allowing for handlers with afvanced feaures, even
        for small snippets, such as proper error messages, automated testing, reificatin etc.
    """

    # methods in delegated are forwarded to delegatees. note that delegatees is static,
    # meaning that every instance of AspSession will use it
    delegated = ('parse', 'control', 'load', 'ground', 'solve', 'logger')
    delegatees = (DefaultHandler(),)

    def __init__(self, source=None, files=None, context=None):
        """ prepare source as string or from files for grounding and solving """
        assert files or source
        self._spent_controls = set()
        self.parameters = parameters = {}
        if source is not None:
            parameters['source'] = source
        if files is not None:
            parameters['files'] = files
        if context is not None:
            parameters['context'] = context
        self.parse(parameters)

    def __call__(self, control=None, parts=None, **solve_options):
        """ combine ground and solve for convenience """
        control = self.go_ground(control=control, parts=parts)
        return self.go_solve(control, **solve_options)

    def go_ground(self, control=None, parts=None):
        """ ground parts into given control; control must be fresh """
        parameters = self.parameters
        if not control:
            control = self.control(parameters)
        if control in self._spent_controls:
            raise ValueError(f"Cannot reuse Control {control}")
        else:
            self._spent_controls.add(control)
        if parts is not None:
            parameters['parts'] = parts
        self.load(control, parameters)
        self.ground(control, parameters)
        return control

    def go_solve(self, control, **solve_options):
        parameters = self.parameters
        if solve_options != {} :
            parameters['solve_options'] = solve_options
        return self.solve(control, parameters)

    def __getitem__(self, name):
        return self.parameters[name]

    def __exit__(self, t, v, tb):
        del self.parameters

    def add_handler(self, handler_name):
        print("Inserting handler:", handler_name, file=sys.stderr)
        modulename, classname = handler_name.split(':')
        module = importlib.import_module(modulename)
        handler_class = getattr(module, classname)
        handler = handler_class()
        self.add_delegatee(handler)
        return handler


@test
def dont_do_this_it_segvs():
    def go():
        c = clingo.Control()
        c.add("a.")
        c.ground()
        return c.symbolic_atoms
    sa = go()
    #segv: list(sa.by_signature('a', 0))


@test
def create_session():
    with AspSession("aap.") as s:
        control = s.go_ground()
        models = list(s.go_solve(control))
        test.eq(['aap'], [str(a.symbol) for a in control.symbolic_atoms.by_signature('aap', 0)])
        models = list(models)
        test.truth(models[0].contains(clingo.Function('aap')))
        test.eq(1, len(models))


@test
def hook_basics():
    class TestHook:
        def prepare(this, self, parameters):
            test.eq(th, this)
            test.eq(app, self)
            test.eq({'42': 42}, parameters)
            return 43
        def parse(this, self, parameters):
            test.eq(th, this)
            test.eq(app, self)
            test.eq({'42': 42}, parameters)
            return 44
        def ground(this, self, parameters):
            test.eq(th, this)
            test.eq(app, self)
            test.eq({'42': 42}, parameters)
            return 45
        def solve(this, self, parameters):
            test.eq(th, this)
            test.eq(app, self)
            test.eq({'42': 42}, parameters)
            return 46
        def logger(this, self, parameters):
            test.eq(th, this)
            test.eq(app, self)
            test.eq({'42': 42}, parameters)
            return 47

    th = TestHook()
    app = AspSession("bee.")
    with app as session:
        session.add_delegatee(th)
        data = {'42': 42}
        test.eq(44, session.parse(data))
        test.eq(45, session.ground(data))
        test.eq(46, session.solve(data))
        test.eq(47, session.logger(data))


# for testing hooks
class TestHaak:
    def ground(this, self, control, parameters):
        control.add('testhook(ground).')
        self.ground(control, parameters)


@test
def add_hook_in_ASP(stderr):
    app = AspSession('processor("asp_selftest.session:TestHaak"). bee.')
    ctl = clingo.Control()
    with app:
        app.go_ground(control=ctl)
        list(app.go_solve(control=ctl))
    test.eq('bee', find_symbol(ctl, "bee"))
    test.eq('testhook(ground)', find_symbol(ctl, "testhook", 1))
    test.eq('Inserting handler: asp_selftest.session:TestHaak\n', stderr.getvalue())


# for testing hooks
class TestHook2:
    def main(this, self, parameters):
        pass  # pragma no cover
    def parse(this, self, parameters):
        pass  # pragma no cover


@test
def hook_in_ASP_is_too_late_for_some_methods(stdout):
    with test.raises(
            AssertionError,
            "'parse' of asp_selftest.session:TestHook2 can never be called.") as e:
        AspSession('processor("asp_selftest.session:TestHook2"). bee.')


@test
def multiple_hooks():
    session = AspSession('boe.')
    class Hook1():
        def ground(this, self, control, parameters):
            control.add('hook_1.')
            self.ground(control, parameters)
    class Hook2():
        def ground(this, self, control, parameters):
            control.add('hook_2.')
            self.ground(control, parameters)
    h1 = Hook1()
    h2 = Hook2()
    session.add_delegatee(h1)
    session.add_delegatee(h2)
    with session:
        control = session.go_ground()
        list(session.go_solve(control=control))
        test.eq('boe', find_symbol(control, "boe"))
        test.eq('hook_1', find_symbol(control, "hook_1"))
        test.eq('hook_2', find_symbol(control, "hook_2"))


@test
def select_parts():
    with AspSession("a. #program p. b. #program q. c.") as s:
        models = list(s(parts=[('base',())]))
        test.truth(models[0].contains(clingo.Function('a')))
        test.not_( models[0].contains(clingo.Function('b')))
        test.not_( models[0].contains(clingo.Function('c')))

        models = list(s(parts=[('p',())], control=clingo.Control()))
        test.not_( models[0].contains(clingo.Function('a')))
        test.truth(models[0].contains(clingo.Function('b')))
        test.not_( models[0].contains(clingo.Function('c')))

        models = list(s(parts=[('q',())], control=clingo.Control()))
        test.not_( models[0].contains(clingo.Function('a')))
        test.not_( models[0].contains(clingo.Function('b')))
        test.truth(models[0].contains(clingo.Function('c')))

        models = list(s(parts=[('base',()), ('p',()), ('q',())], control=clingo.Control()))
        test.truth(models[0].contains(clingo.Function('a')))
        test.truth(models[0].contains(clingo.Function('b')))
        test.truth(models[0].contains(clingo.Function('c')))
