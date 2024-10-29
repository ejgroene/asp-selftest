
""" WIP: Clingo drop-in replacement with support for tests and hooks """


import sys
import types
import functools
import importlib
import argparse
import inspect


import clingo
from clingo import Control, Application, clingo_main
from clingo.script import enable_python
enable_python()


from .utils import is_processor_predicate


import selftest
test = selftest.get_tester(__name__)


def main_main(programs, remaining, hooks):
    programs and print("Grounding programs:", programs)
    app = MainApp(programs=programs, hooks=hooks)
    clingo_main(app, remaining)
    app.check()

def locals(name):
    f = inspect.currentframe().f_back
    while f := f.f_back:
        if value := f.f_locals.get(name):
            yield value


@test
def find_locals():
    l = 1
    test.eq([], list(locals('l')))
    def f():
        l = 2
        test.eq([1], list(locals('l')))
    f()


def delegate(function):
    """ Decorator for delegating methods to processors """
    @functools.wraps(function)
    def dispatch(self, *args, **kwargs):
        __mark__ = 1
        for obj in self.delegates:
            if handler := getattr(obj, function.__name__, None):
                if handler in locals('handler'):
                    continue
                return handler(self, *args, **kwargs)
        seen = ', '.join(sorted(set(l.__qualname__ for l in locals('handler'))))
        raise AttributeError(f"No more {function.__name__!r} found after: {seen}")
    active = dispatch
    return dispatch


@test
def delegation_none():
    class B:
        delegates = ()
        @delegate
        def f(self):
            pass
    with test.raises(AttributeError):
        B().f()


@test
def delegation_one():
    class A:
        def f(this, self):
            return this, self
    a = A()
    class B:
        delegates = (a,)
        @delegate
        def f(self):
            pass
    b = B()
    test.eq((a, b), b.f())


@test
def delegation_loop():
    class A:
        def f(this, self):
            return self.f()
    a = A()
    class B:
        delegates = (a,)
        @delegate
        def f(self):
            pass
    with test.raises(AttributeError):
        B().f()


@test
def delegation_loop_back_forth():
    class A:
        def f(this, self):
            return self.f()
    a = A()
    class B:
        def f(this, self):
            return self.f()
    b = B()
    class C:
        delegates = (a, b)
        @delegate
        def f(self):
            pass
    with test.raises(
            AttributeError,
            "No more 'f' found after: delegation_loop_back_forth.<locals>.A.f, delegation_loop_back_forth.<locals>.B.f"):
        C().f()


@test
def delegation():
    class B:
        def f(this, self):
            return self.g() * self.h() * this.i() # 5 * 3 * 2
        def h(this, self):
            return 3
        def i(self):
            return 2
    class C:
        def g(this, self):
            return 5
        def i(this, self):
            return 7
    class A:
        delegates = [B(), C()]
        @delegate
        def f(self):
            pass
        @delegate
        def h(self):
            pass
        @delegate
        def g(self):
            pass
        @delegate
        def i(self):
            pass
    test.eq(30, A().f())



class DefaultHook:

    def __init__(self, programs):
        self._programs = [(p, ()) for p in programs or ()]

    def message_limit(this, self):
        return 10

    def main(this, self, ctl, files):
        ast = []
        self.parse(ctl, files, ast.append)
        self.load(ctl, ast)
        self.ground(ctl, [('base', ())] + this._programs, context=None)
        self.solve(ctl)

    def parse(this, self, ctl, files, on_ast):
        def add(ast):
            if p := is_processor_predicate(ast):
                print("Inserting processor:", p)
                modulename, classname = p.split(':')
                mod = importlib.import_module(modulename)
                processor_class = getattr(mod, classname)
                processor = processor_class(self, ctl)
                for m in ('message_limit', 'main', 'parse'):
                    assert not hasattr(processor, m), f"{m!r} of {p} can never be called."
                self.delegates.insert(-1, processor)
            on_ast(ast)
        clingo.ast.parse_files(files, callback=add, logger=self.logger, message_limit=self.message_limit)

    def load(this, self, ctl, ast):
        with clingo.ast.ProgramBuilder(ctl) as pb:
            for a in ast:
                pb.add(a)

    def ground(this, self, ctl, parts, context):
        ctl.ground(parts, context=context)

    def solve(this, self, control, *a, **k):
        control.solve(*a, **k)

    def logger(this, self, code, message):
        # should not raise exceptions
        return code, message # pragma no cover

    def print_model(this, self, model, printer):
        printer()

    def check(this, self):
        raise NotImplementedError("check")  # pragma no cover


import functools
import traceback
def guard(f):
    @functools.wraps(f)
    def wrap(*a, **k):
        try:
            return f(*a, **k)
        except Exception as e:
            print(f"{f.__qualname__} must not raise exceptions. It did.", file=sys.stderr)
            traceback.print_exc()
            exit(-1)
    return wrap


class MainApp(Application):

    def __init__(self, programs=None, hooks=()):
        self.delegates = list(hooks) + [DefaultHook(programs)]
        self.program_name = "clingo+tests"
        Application.__init__(self)

    @property
    @delegate
    def message_limit(self):
        raise NotImplementedError("message_limit")  # pragma no cover

    @delegate
    def main(self, ctl, files):
        raise NotImplementedError("main")  # pragma no cover

    @delegate
    def parse(self, ctl, files, on_ast):
        raise NotImplementedError("parse")  # pragma no cover

    @delegate
    def load(self, ctl, ast):
        raise NotImplementedError("load")  # pragma no cover

    @delegate
    def ground(self, ctl, parts, context):
        raise NotImplementedError("ground")  # pragma no cover
        
    @delegate
    def solve(self, control):
        raise NotImplementedError("solve")  # pragma no cover

    @delegate
    def logger(self, code, message):
        raise NotImplementedError("logger")  # pragma no cover

    @delegate
    def print_model(self, model, printer):
        raise NotImplementedError("print_model")  # pragma no cover

    @delegate
    def check(self):
        raise NotImplementedError("check")  # pragma no cover


def find_symbol(ctl, name, arity=0):
    return str(next(ctl.symbolic_atoms.by_signature(name, arity)).symbol)


@test
def main_clingo_app(tmp_path):
    f = tmp_path/"f"
    f.write_text("ape.")
    app = MainApp()
    test.isinstance(app, Application)
    test.eq('clingo+tests', app.program_name)
    test.eq(10, app.message_limit)
    ctl = Control()
    app.main(ctl, [f.as_posix()])
    test.eq('ape', find_symbol(ctl, "ape"))


@test
def hook_basics(tmp_path):
    f = tmp_path/"f"
    f.write_text('bee.')
    class TestHook:
        def message_limit(this, self):
            return 42
        def main(this, self, ctl, files):
            test.eq(th, this)
            test.eq(app, self)
            test.eq('a control', ctl)
            test.eq('files', files)
            return 43
        def parse(this, self, ctl, files):
            test.eq(th, this)
            test.eq(app, self)
            test.eq('a control', ctl)
            test.eq('files', files)
            return 44
        def ground(this, self, ctl, parts, context):
            test.eq(th, this)
            test.eq(app, self)
            test.eq('a control', ctl)
            test.eq('parts', parts)
            test.eq('a context', context)
            return 45
        def solve(this, self, ctl):
            test.eq(th, this)
            test.eq(app, self)
            test.eq('a control', ctl)
            return 46
        def logger(this, self, code, message):
            test.eq(th, this)
            test.eq(app, self)
            test.eq('a code', code)
            test.eq('a msg', message)
            return 47
        def print_model(this, self, model, printer):
            test.eq(th, this)
            test.eq(app, self)
            test.eq('a model', model)
            test.eq('a printer', printer)
            return 48

    th = TestHook()
    app = MainApp(hooks=[th])
    test.eq(42, app.message_limit)
    test.eq(43, app.main("a control", "files"))
    test.eq(44, app.parse("a control", "files"))
    test.eq(45, app.ground("a control", "parts", "a context"))
    test.eq(46, app.solve("a control"))
    test.eq(47, app.logger("a code", "a msg"))
    test.eq(48, app.print_model("a model", "a printer"))


# for testing hooks
class TestHaak:
    def __init__(self, app, control):
        pass
    def ground(this, self, ctl, parts, context):
        ctl.add('testhook(ground).')
        self.ground(ctl, parts, context)


@test
def add_hook_in_ASP(tmp_path, stdout):
    f = tmp_path/"f"
    f.write_text('processor("asp_selftest.application:TestHaak"). bee.')
    app = MainApp()
    ctl = Control()
    app.main(ctl, [f.as_posix()])
    test.eq('bee', find_symbol(ctl, "bee"))
    #test.eq([], app.delegates)
    test.eq('testhook(ground)', find_symbol(ctl, "testhook", 1))
    #test.eq('Adding processor: asp_selftest.application:TestHook\n', stdout.getvalue())



# for testing hooks
class TestHook2:
    def __init__(self, app, control):
        pass
    def message_limit(self, prev):
        pass  # pragma no cover
    def main(self, prev, ctl, files):
        pass  # pragma no cover
    def parse(self, prev, ctl, files):
        pass  # pragma no cover


@test
def hook_in_ASP_is_too_late_for_some_methods(tmp_path, stdout):
    f = tmp_path/"f"
    f.write_text('processor("asp_selftest.application:TestHook2"). bee.')
    app = MainApp()
    ctl = Control()
    with test.raises(
            AssertionError,
            "'message_limit' of asp_selftest.application:TestHook2 can never be called.") as e:
        app.main(ctl, [f.as_posix()])


@test
def multiple_hooks(tmp_path):
    f = tmp_path/"f"
    f.write_text('boe.')
    class Hook1():
        def ground(this, self, ctl, parts, context):
            ctl.add('hook_1.')
            self.ground(ctl, parts, context)
    class Hook2():
        def ground(this, self, ctl, parts, context):
            ctl.add('hook_2.')
            self.ground(ctl, parts, context)
    h1 = Hook1()
    h2 = Hook2()
    app = MainApp(hooks=[h1, h2])
    ctl = Control()
    app.main(ctl, [f.as_posix()])
    test.eq('boe', find_symbol(ctl, "boe"))
    test.eq('hook_1', find_symbol(ctl, "hook_1"))
    test.eq('hook_2', find_symbol(ctl, "hook_2"))

