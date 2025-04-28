import pathlib
import subprocess
import os
import functools

import clingo
import selftest

test = selftest.get_tester(__name__)


class Main:
    """ Main Application dictated by Clingo, to be fed to clingo_main() """
    def main(self, control, files):
        clingo_session(files=files, control=control)


def Noop(next, *args):
    return next(*args)


def default_control(control=None, arguments=(), logger=None, message_limit=20, **etc):
    """ Creates a Control when none is given (when used without clingo_main)."""

    if control is None:
        my_control = clingo.Control(arguments=arguments, logger=logger, message_limit=message_limit)

    def load(next, control):
        next(control or my_control)
                    
    def ground(next, control, parts):
        next(control or my_control, parts)
                
    def solve(next, control):
        return next(control or my_control)

    return load, ground, solve


def clingo_default_control(files=(), context=None, yield_=False, **etc):
    """ Controller implementing the default Clingo behaviour. """

    def load(next, control):
        for f in files:
            control.load(f)
        if not files:
            control.load("-")
                    
    def ground(next, control, parts):
        control.ground(parts=parts, context=context)
                
    def solve(next, control):
        return control.solve(on_model=None, yield_=yield_)

    return load, ground, solve

    
def source_support_control(source=None, **etc):
    """ Loads source given as string. """

    def load(next, control):
        if source:
            control.add(source)
        else:
            next(control)

    return load, Noop, Noop


controllers = [default_control,
               source_support_control,
               clingo_default_control]
   
    
def clingo_session(
        source=None,
        files=(),
        control=None,
        message_limit=20,
        parts=(('base', ()),),
        context=None,
        logger=None,
        arguments=None,
        yield_=False):

    controller_functions = [
        controller(control=control,
                   source=source,
                   context=context,
                   yield_=yield_)
            for controller in controllers]

    def call(i, n, *args):
        func = controller_functions[i][n]
        return func(functools.partial(call, i+1, n), *args)

    call(0, 0, control)
    call(0, 1, control, parts)
    return call(0, 2, control)
        

# entry point
def clingo_plus_main_ng():
    clingo.application.clingo_main(Main(), arguments=())


def run_clingo_plus_main(code):
    path = pathlib.Path(__file__).parent
    return subprocess.run(
        ["python", "-c", f"from sessionng import clingo_plus_main_ng; clingo_plus_main_ng()"],
        env=os.environ | {'PYTHONPATH': path},
        input=code,
        capture_output=False)
        
@test
def from_clingo_main(stdout):
    run_clingo_plus_main(b"owkee. #program test_owkee(base).")
    test.startswith(stdout.getvalue(), 'clingo version 5.7.1\nReading from stdin\nSolving...\nAnswer: 1\nowkee\nSATISFIABLE')
    
        
@test
def test_simple():
    result = clingo_session(source="a.")
    test.truth(result.satisfiable)


