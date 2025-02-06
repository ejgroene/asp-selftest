
import functools
import contextlib


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

    @staticmethod
    def guard(f):
        @functools.wraps(f)
        def guarding(self, *a, **k):
            try:
                return f(self, *a, **k)
            except Exception as e:
                if previous_exc := getattr(self, '_exception', False):
                    previous_exc.add_note(f"(followed by {e!r})")
                else:
                    self._exception = e
        return guarding


    def __getattribute__(self, name):
        if name != '_context_active':
            assert self._context_active, f"only to be used as context manager"
        return object.__getattribute__(self, name)


    def __enter__(self):
        assert not self._context_active, "Cannot reuse {self}."
        self._context_active = True
        return self


    def __exit__(self, exc_type, exc_value, exc_traceback):
        if not exc_type and hasattr(self, '_exception'):
            raise self._exception


@test
def guard_against_use_without_with():
    class A(ExceptionGuard):
        def f(self):
            pass
    a = A()
    with test.raises(AssertionError, "only to be used as context manager"):
        a.f()


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
    test.eq(["(followed by RuntimeError('parsing failed'))"], e.exception.__notes__)
    test.startswith(stdout.getvalue(), "clingo version ")


@test
def do_not_mask_other_exceptions(stdout):
    class App(Application, ExceptionGuard):
        @ExceptionGuard.guard
        def main(self, control, files):
            raise RuntimeError("HELP")
    app = App()
    with test.raises(NameError, "name 'this_raises' is not defined"):
        with app:
            clingo_main(app, ['nothere.lp'])
            this_raises
    test.startswith(stdout.getvalue(), "clingo version ")
