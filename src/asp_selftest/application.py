
""" WIP: Clingo drop-in replacement with support for tests and hooks """


import sys
import types
import functools
import importlib
import argparse


import clingo
from clingo import Control, Application, clingo_main
from clingo.script import enable_python
enable_python()


from .utils import is_processor_predicate


import selftest
test = selftest.get_tester(__name__)


def delegate(function):
    """ Decorator for delegating methods to processors """
    @functools.wraps(function)
    def f(self, *args, **kwargs):
        prev = types.MethodType(function, self)
        fsp = self.first_stage_processors
        handlers = [getattr(p, function.__name__) for p in fsp if hasattr(p, function.__name__)]
        if not handlers:
            return prev(*args, **kwargs)
        if len(handlers) > 1:
            prev = types.MethodType(handlers[-2], prev)
        return handlers[-1](prev, *args, **kwargs) 
    return f


class MainApp(Application):

    def __init__(self, programs=None, hooks=()):
        self.first_stage_processors = list(hooks)
        self.program_name = "clingo+tests"
        self._programs = [(p, ()) for p in programs or ()]
        Application.__init__(self)

    @property
    @delegate
    def message_limit(self):
        return 10

    @delegate
    def main(self, ctl, files):
        ast = []
        self.parse(ctl, files, ast.append)
        self.load(ctl, ast)
        self.ground(ctl, [('base', ())] + self._programs, context=None)
        self.solve(ctl)

    @delegate
    def parse(self, ctl, files, on_ast):
        def add(ast):
            if p := is_processor_predicate(ast):
                print("Adding processor:", p)
                modulename, classname = p.split(':')
                mod = importlib.import_module(modulename)
                processor_class = getattr(mod, classname)
                processor = processor_class(self, ctl)
                for m in ('message_limit', 'main', 'parse'):
                    assert not hasattr(processor, m), f"{m!r} of {p} can never be called."
                self.first_stage_processors.append(processor)
            on_ast(ast)
        clingo.ast.parse_files(files, callback=add, logger=self.logger, message_limit=self.message_limit)

    @delegate
    def load(self, ctl, ast):
        with clingo.ast.ProgramBuilder(ctl) as pb:
            for a in ast:
                pb.add(a)

    @delegate
    def ground(self, ctl, parts, context):
        ctl.ground(parts, context=context)
        
    @delegate
    def solve(self, control):
        control.solve()

    @delegate
    def logger(self, code, message):
        raise Exception("NYI logger")  # pragma no cover

    @delegate
    def print_model(self, model, printer):
        printer()

    @delegate
    def check(self):
        raise Exception("NYI check")  # pragma no cover

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
        def message_limit(self, prev):
            return 42
        def main(self, prev, ctl, files):
            test.eq(app, prev.__self__)
            test.eq('main', prev.__name__)
            test.eq('a control', ctl)
            test.eq('files', files)
            return 43
        def parse(self, prev, ctl, files):
            test.eq(app, prev.__self__)
            test.eq('parse', prev.__name__)
            test.eq('a control', ctl)
            test.eq('files', files)
            return 44
        def ground(self, prev, ctl, parts, context):
            test.eq(app, prev.__self__)
            test.eq('ground', prev.__name__)
            test.eq('a control', ctl)
            test.eq('parts', parts)
            test.eq('a context', context)
            return 45
        def solve(self, prev, ctl):
            test.eq(app, prev.__self__)
            test.eq('solve', prev.__name__)
            test.eq('a control', ctl)
            return 46
        def logger(self, prev, code, message):
            test.eq(app, prev.__self__)
            test.eq('logger', prev.__name__)
            test.eq('a code', code)
            test.eq('a msg', message)
            return 47
        def print_model(self, prev, model, printer):
            test.eq(app, prev.__self__)
            test.eq('print_model', prev.__name__)
            test.eq('a model', model)
            test.eq('a printer', printer)
            return 48

    app = MainApp(hooks=[TestHook()])
    test.eq(42, app.message_limit)
    test.eq(43, app.main("a control", "files"))
    test.eq(44, app.parse("a control", "files"))
    test.eq(45, app.ground("a control", "parts", "a context"))
    test.eq(46, app.solve("a control"))
    test.eq(47, app.logger("a code", "a msg"))
    test.eq(48, app.print_model("a model", "a printer"))


# for testing hooks
class TestHook:
    def __init__(self, app, control):
        pass
    def ground(self, prev, ctl, parts, context):
        ctl.add('testhook(ground).')
        prev(ctl, parts, context)


@test
def add_hook_in_ASP(tmp_path, stdout):
    f = tmp_path/"f"
    f.write_text('processor("asp_selftest.application:TestHook"). bee.')
    app = MainApp()
    ctl = Control()
    app.main(ctl, [f.as_posix()])
    test.eq('bee', find_symbol(ctl, "bee"))
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
        def ground(self, prev, ctl, parts, context):
            test.eq(app, prev.__self__)
            ctl.add('hook_1.')
            prev(ctl, parts, context)
            return 'hook 1'
    class Hook2():
        def ground(self, prev, ctl, parts, context):
            ctl.add('hook_2.')
            response = prev(ctl, parts, context)
            test.eq('hook 1', response)
    h1 = Hook1()
    h2 = Hook2()
    app = MainApp(hooks=[h1, h2])
    ctl = Control()
    app.main(ctl, [f.as_posix()])
    test.eq('boe', find_symbol(ctl, "boe"))
    test.eq('hook_1', find_symbol(ctl, "hook_1"))
    test.eq('hook_2', find_symbol(ctl, "hook_2"))

