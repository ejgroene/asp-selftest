#!/usr/bin/env python3
import sys
import types
import tempfile
import importlib
import argparse
import clingo
from clingo import Control, Application, clingo_main

from clingo.script import enable_python
enable_python()


from .error_handling import warn2raise, AspSyntaxError
from .utils import is_processor_predicate
from .reify import Reify

first_stage_processors = []

def processor(obj):
    first_stage_processors.append(obj)


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
    """ Decorator for delegating methods to processors """
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

    def __init__(self, programs=None):
        self._programs = [(p, ()) for p in programs or ()]
        Application.__init__(self)

    @property
    @delegate
    def message_limit(self):
        return 10

    @delegate
    def main(self, ctl, files):
        self.parse(ctl, files)
        #self.load(ctl, files)
        self.ground(ctl, [('base', ())] + self._programs)
        self.solve(ctl)

    @delegate
    def parse(self, ctl, files):
        with clingo.ast.ProgramBuilder(ctl) as pb:
            def add(ast):
                if p := is_processor_predicate(ast):
                    print("Adding processor:", p)
                    first_stage_processors.append(globals()[p]())
                pb.add(ast)
            clingo.ast.parse_files(files, callback=add)

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
    """ Add --programs option + testing and ground/solve as stock Clingo as much as possible. """
    args = argparse.ArgumentParser(add_help=False, exit_on_error=False, allow_abbrev=False)
    args.add_argument('-p', '--programs', nargs='+', help="specify #program's to ground")
    opts, remaining = args.parse_known_args()
    opts.programs and print("Grounding programs:", opts.programs)
    app = MainApp(programs=opts.programs)
    r =  clingo_main(app, remaining)
    app.check()


