
""" WIP: Clingo drop-in replacement with support for tests and hooks """


import sys
import clingo


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


class SyntaxErrors:

    def __init__(self):
        self.exceptions = []

    def message_limit(self, prev):
        return 1

    def main(self, prev, ctl, files):
        try:
            prev(ctl, files)
        except Exception as e:
            if not self.exceptions:
                self.exceptions.append(e)

    def logger(self, prev, code, message):
        lines = self.input.splitlines() if hasattr(self, 'input') else None
        label = '<stdin>' if lines else None
        warn2raise(lines, label, self.exceptions, code, message)

    def check(self, prev):
        if self.exceptions:
            raise self.exceptions[0]
