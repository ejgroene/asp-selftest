
""" WIP: Clingo drop-in replacement with support for tests and hooks """


import sys
import clingo
import functools


from .error_handling import warn2raise, AspSyntaxError


import selftest
test = selftest.get_tester(__name__)



class PrintGroundSymbols:

    def ground(self, prev, ctl, parts, context=None):
        print("=== symbols ===")
        prev(ctl, parts, context)
        for s in ctl.symbolic_atoms:
            print(s.symbol)
        print("=== end symbols ===")


def save_exception(f):
    @functools.wraps(f)
    def wrap(self, *a, **k):
        try:
            if self.exception:
                return # we quit the process early, as these could yield more errors
            return f(self, *a, **k)
        except RuntimeError as e:
            if self.exception:
                raise self.exception
            else:
                raise
    return wrap


class SyntaxErrors:

    def __init__(this):
        this.exception = None
        this._suppress = None

    def message_limit(this, self):
        return 1

    @save_exception
    def parse(this, self, ctl, files, on_ast):
        self.parse(ctl, files, on_ast)

    @save_exception
    def load(this, self, ctl, ast, parts=None):
        self.load(ctl, ast, parts=parts)

    @save_exception
    def ground(this, self, ctl, parts, context):
        self.ground(ctl, parts, context)

    def logger(this, self, code, message):
        self.logger(code, message)
        if code == clingo.MessageCode.FileIncluded:
            # always ignore duplicate includes, only warn. @TODO TESTME
            print("Ignoring duplicate #include:", message, file=sys.stderr)
            return
        if this._suppress == code:
            this._suppress = None
            return
        if this.exception:
            print("  WARNING ALREADY exception:", this.exception, file=sys.stdout)
            print("               while logging:", message, file=sys.stdout)
        else:
            this.exception = warn2raise(None, None, code, message)

    def suppress_logger(this, self, code):
        this._suppress = code

    def check(this, self):
        self.check()
        if this.exception:
            try:
                raise this.exception
            finally:
                this.exception = None

