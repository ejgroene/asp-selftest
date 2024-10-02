#!/usr/bin/env python3
import sys
import types
import tempfile
import clingo
from clingo import Control, Application, clingo_main
import importlib

from clingo.script import enable_python
enable_python()


from error_handling import warn2raise, AspSyntaxError

first_stage_processors = []

def tstr(l):
    return tuple(map(str,l))

def processor(obj):
    first_stage_processors.append(obj)


class Reify:
    #REIFY_THEORY = "#theory reify {term {}; &reify/0: term, head}."

    def ground(self, prev, ctl, parts, context=None):
        #ctl.add(self.REIFY_THEORY)
        prev(ctl, parts, context)
        reified = set()
        def get_reifies():
            return {tstr(s.symbol.arguments) for s in ctl.symbolic_atoms if s.symbol.name == 'reify'}
        reifies = get_reifies()
        while reifies > reified:
            with tempfile.NamedTemporaryFile(mode='w', prefix='reify-', suffix='.lp') as f:
                for function, *arguments in reifies:
                    atom = f"{function}({'.'.join(arguments)}).\n"
                    print("REIFY:", atom)
                    f.write(atom)
                f.flush()
                ctl.load(f.name)
                prev(ctl, parts, context)
                reified = reifies
                reifies = get_reifies()


class PrintGroundSymbols:
    def ground(self, prev, ctl, parts, context=None):
        print("=== symbols ===")
        prev(ctl, parts, context)
        for s in ctl.symbolic_atoms:
            print(s.symbol)
        print("=== end symbols ===")


class SyntaxErrors:

    exceptions = []

    def message_limit(self, prev):
        return 1

    def main(self, prev, ctl, files):
        try:
            prev(ctl, files)
        except Exception as e:
            assert self.exceptions

    def load(self, prev, ctl, files):
        if files:
            prev(ctl, files)
        else:
            self.input = sys.stdin.read()
            ctl.add(self.input)

    def logger(self, prev, code, message):
        lines = self.input.splitlines() if hasattr(self, 'input') else None
        label = '<stdin>' if lines else None
        warn2raise(lines, label, self.exceptions, code, message)

    def check(self, prev):
        if self.exceptions:
            e = self.exceptions[0]
            if isinstance(e, AspSyntaxError):
                sys.tracebacklimit = 0
            raise e

processor(SyntaxErrors())

def delegate(function):
    def f(self, *args, **kwargs):
        prev = types.MethodType(function, self)
        handlers = [getattr(p, function.__name__) for p in first_stage_processors if hasattr(p, function.__name__)]
        if not handlers:
            return prev(*args, **kwargs)
        if len(handlers) > 1:
            prev = types.MethodType(handlers[-2], prev)
        return handlers[-1](prev, *args, **kwargs) 
    return f


class MainApp(Application):

    @property
    @delegate
    def message_limit(self):
        return 10

    @delegate
    def main(self, ctl, files):
        self.load(ctl, files)
        self.ground(ctl, (('base',()),))
        self.solve(ctl)

    @delegate
    def load(self, ctl, files):
        for f in files:
            ctl.load(f)                       # <= 1. scripts executed
                                              #    2. syntax errors logged
        if not files:
            ctl.load("-")

    @delegate
    def ground(self, ctl, parts, context=None):
        ctl.ground(parts)
        
    @delegate
    def solve(self, *args, **kwargs):
        pass

    @delegate
    def logger(self, code, message):
        pass

    @delegate
    def print_model(self, model, printer):
        pass

    @delegate
    def check(self, prev):
        pass


if __name__ == '__main__':
    app = MainApp()
    r =  clingo_main(app, sys.argv[1:])  # *. we want to manipulate arguments
    app.check()


