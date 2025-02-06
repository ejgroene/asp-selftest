""" WIP: Clingo drop-in replacement with support for tests and hooks """


import sys
import importlib
import contextlib
import functools

import clingo
from clingo import Control, Application, clingo_main

from clingo.script import enable_python
enable_python()


from .utils import is_processor_predicate, delegate, find_symbol


import selftest
test = selftest.get_tester(__name__)


def main_main(programs, arguments, hooks):
    programs and print("Grounding programs:", programs)
    with MainApp(programs=programs, hooks=hooks, arguments=arguments) as app:
        clingo_main(app, arguments)


class DefaultHook:
    """ Implements the standard behaviour of grounding and solving ASP programs.
        It supports adding hooks during parsing.
    """

    def __init__(self, programs):
        self._programs = [(p, ()) for p in programs or ()]

    def _add_processor(this, self, p, ctl):
        #TODO check for duplicates?
        print("Inserting processor:", p, file=sys.stderr)
        modulename, classname = p.split(':')
        mod = importlib.import_module(modulename)
        processor_class = getattr(mod, classname)
        processor = processor_class(self)
        for m in ('message_limit', 'main', 'parse'):
            assert not hasattr(processor, m), f"{m!r} of {p} can never be called."
        self.delegates.insert(-1, processor)   # TODO we should not know about delegetes here!
        # unless we make it an API, which is not a crazy idea, because we are part of the 
        # collective, and extending it makes sense (we're also the defaul/system hook....)

    def message_limit(this, self):
        return 10

    def main(this, self, ctl, files):
        """ Template method sequencing through all steps. """
        ast = []
        self.parse(ctl, files, ast.append)
        self.load(ctl, ast)
        self.ground(ctl, [('base', ())] + this._programs, context=None)
        self.solve(ctl)

    def parse(this, self, ctl, files, on_ast):
        def add(ast):
            if p := is_processor_predicate(ast):
                this._add_processor(self, p, ctl)
            on_ast(ast)
        clingo.ast.parse_files(files, callback=add, logger=self.logger, message_limit=self.message_limit)

    def load(this, self, ctl, ast, parts=None):
        with clingo.ast.ProgramBuilder(ctl) as pb:
            for a in ast:
                try:
                    pb.add(a)
                except Exception as e:
                    e.add_note(str(a))
                    raise e from None


    def ground(this, self, ctl, parts, context):
        ctl.ground(parts, context=context)

    def solve(this, self, control, *a, **k):
        control.solve(*a, **k)

    def logger(this, self, code, message):
        pass

    def print_model(this, self, model, printer):
        printer()

    def check(this, self):
        pass


def clingo_called(f):
    @functools.wraps(f)
    def wrap(self, *a, **k):
        assert self._context_active, \
            f"{f.__qualname__} must be run like: with MainApp() as m: m.{f.__name__}(...)"
        try:
            return f(self, *a, **k)
        except Exception as e:
            if self._exception:  # and error has been logged, but another error occurred
                raise
            self._exception = e
    return wrap


class MainApp(Application, contextlib.AbstractContextManager):
    """ Clingo Main application.

        It follows Clingo's implementation except that is uses an explict parse 
        and load step in order to interecept processing as early as during parse.

        It uses delegation instead of inheritance to dynamically add additional
        objects (hooks) that can refine the methods called by Clingo.

        The default behaviour is in the last hook: DefaultHook. It defines a
        template methode for main() which sequences through parse, load, ground
        and solve.

        Because methods called by Clingo must not raise exceptions, all such methods
        are marked by clingo_called. Because main() can also not raise exceptions,
        we collect exceptions and raise them afterwards in check().
    """

    def __init__(self, programs=None, hooks=(), trace=None, arguments=()):
        self.programs = programs
        self.delegates = list(hooks) + [DefaultHook(programs)]
        self.program_name = "clingo+tests"
        self.trace = trace or (lambda *a, **k: None)
        self._context_active = False
        self._exception = None
        self.arguments = arguments
        Application.__init__(self)

    @property
    @clingo_called
    @delegate
    def message_limit(self):
        raise NotImplementedError("message_limit")  # pragma no cover

    @clingo_called
    @delegate
    def logger(self, code, message):
        raise NotImplementedError("logger")  # pragma no cover

    @delegate
    def suppress_logger(self, code):
        raise NotImplementedError("suppress_logger")  # pragma no cover

    @clingo_called
    @delegate
    def print_model(self, model, printer):
        raise NotImplementedError("print_model")  # pragma no cover

    @clingo_called
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
    def check(self):
        raise NotImplementedError("check")  # pragma no cover

    def __enter__(self):
        self._context_active = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # exceptions here could be programming errors
        #assert not exc_value, f"Got exception: {exc_value}"
        self._context_active = False
        if self._exception:
            raise self._exception
        self.check()


@test
def main_clingo_app(tmp_path):
    f = tmp_path/"f"
    f.write_text("ape.")
    app = MainApp()
    test.isinstance(app, Application)
    with app:
        test.eq('clingo+tests', app.program_name)
        test.eq(10, app.message_limit)
        ctl = Control()
        app.main(ctl, [f.as_posix()])
        test.eq('ape', find_symbol(ctl, "ape"))

