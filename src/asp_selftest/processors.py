
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


class Stop(Exception):
    pass


def save_exception(f):
    @functools.wraps(f)
    def wrap(self, *a, **k):
        try:
            return f(self, *a, **k)
        except RuntimeError as e:
            # uncomment when you loose errors during use
            #print(f"{f.__qualname__} got exception:", e)
            assert len(self.exceptions) == 1
    return wrap


class SyntaxErrors:

    def __init__(this):
        this.exceptions = []

    def message_limit(this, self):
        return 1

    @save_exception
    def main(this, self, ctl, files):
        try:
            self.main(ctl, files)
        except Stop:
            #raise this.exceptions[0] from None
            pass
        finally:
            #this.exceptions.clear()
            pass

    @save_exception
    def parse(this, self, ctl, files, on_ast):
        self.parse(ctl, files, on_ast)
        if this.exceptions:
            raise Stop

    @save_exception
    def load(this, self, ctl, ast):
        self.load(ctl, ast)
        if this.exceptions:
            raise Stop

    @save_exception
    def ground(this, self, ctl, parts, context):
        self.ground(ctl, parts, context)
        if this.exceptions:
            raise Stop

    @save_exception
    def solve(this, self, control, *a, **k):
        self.solve(control, *a , **k)
        if this.exceptions:
            raise Stop

    def logger(this, self, code, message):
        results = self.logger(code, message)
        if results:
            label = '<stdin>'
            warn2raise(None, label, this.exceptions, *results)

    def check(this, self):
        if this.exceptions:
            if len(this.exceptions) > 1:
                print("================= multiple exceptions =============")
                for e in this.exceptions:
                    print(e)
            raise this.exceptions[-1] from None
