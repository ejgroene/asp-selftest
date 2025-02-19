
import functools
import contextlib
import inspect
import traceback
import sys


import clingo
from clingo import Control, Application, clingo_main


import selftest
test = selftest.get_tester(__name__)


class ExceptionGuard(contextlib.AbstractContextManager):
    """ Base class that catches exceptions of certain methods to
        raise these later, on exiting the context. This is useful
        for methods called from C that must not raise exceptions.
    """

    _context_active = False
    _guarded_functions = []

    @staticmethod
    def guard(function):
        ExceptionGuard._guarded_functions.append(function)
        @functools.wraps(function)
        def guarding(self, *a, **k):
            try:
                return function(self, *a, **k)
            except Exception as e:
                if previous_exc := getattr(self, '_exception', False):
                    note = f"(followed by {type(e).__name__}: {e})"
                    previous_exc.add_note(note)
                else:
                    e.add_note(f"Earlier raised by {function.__qualname__}")
                    self._exception = e
        return guarding


    def __getattribute__(self, name):
        attr =  object.__getattribute__(self, name)
        if inspect.ismethod(attr):
            f = getattr(attr.__func__,'__wrapped__', None)
            if f in ExceptionGuard._guarded_functions and not self._context_active:
                raise AssertionError(f"{f.__qualname__} only to be called within a context manager")
        return attr


    def __enter__(self):
        assert not self._context_active, "Cannot reuse {self}."
        self._context_active = True
        return self


    def __exit__(self, exc_type, exc_value, exc_traceback):
        if hasattr(self, '_exception'):
            if exc_value:
                self._exception.add_note(f"followed by: {exc_value}")
            raise self._exception


@test
def enforce_with():
    class A(ExceptionGuard):
        def f(self):
            return 42
        @ExceptionGuard.guard
        def g(self):
            pass
    a = A()
    test.eq(42, a.f())
    with test.raises(AssertionError, "enforce_with.<locals>.A.g only to be called within a context manager"):
        a.g()


@test
def clingo_main_exception(stdout):
    class App(Application, ExceptionGuard):
        @ExceptionGuard.guard
        def main(self, control, files):
            raise RuntimeError("HELP")
    app = App()
    with test.raises(RuntimeError, "HELP"):
        with app:
            clingo_main(app, ['nothere.lp'])
    test.startswith(stdout.getvalue(), "clingo version ")


@test
def clingo_logger_exception(tmp_path, stdout):
    class App(Application, ExceptionGuard):
        @ExceptionGuard.guard
        def main(self, control, files):
            control.add(files[0])       # 2. then it raises RuntimeError(parsing failed)
        @ExceptionGuard.guard
        def logger(self, code, msg):    # 1. it logs syntax error, unexpected EOF
            raise SyntaxError("first exception")
    (tmp_path/'test.lp').write_text("syntax error")
    app = App()
    with test.raises(SyntaxError, "first exception") as e:
        with app:
            clingo_main(app, ['test.lp'])
    test.eq("Earlier raised by clingo_logger_exception.<locals>.App.logger", e.exception.__notes__[0])
    test.eq("(followed by RuntimeError: parsing failed)", e.exception.__notes__[1])
    test.startswith(stdout.getvalue(), "clingo version ")


@test
def do_not_mask_other_exceptions(stdout):
    class App(Application, ExceptionGuard):
        @ExceptionGuard.guard
        def main(self, control, files):
            raise RuntimeError("HELP")
    app = App()
    with test.raises(RuntimeError, "HELP") as e:
        with app:
            clingo_main(app, ['nothere.lp'])
            this_raises
    test.eq("Earlier raised by do_not_mask_other_exceptions.<locals>.App.main", e.exception.__notes__[0])
    test.eq("followed by: name 'this_raises' is not defined", e.exception.__notes__[1])
    test.startswith(stdout.getvalue(), "clingo version ")
