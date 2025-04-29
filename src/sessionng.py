import pathlib
import subprocess
import os
import sys
import functools

import clingo
import selftest

test = selftest.get_tester(__name__)


class Main:
    """ Main Application dictated by Clingo, to be fed to clingo_main() """
    program_name = "clingo+"
    message_limit = 20

    def main(self, control, files):
        clingo_session(control=control, files=files, logger=self.logger, message_limit=self.message_limit)

    #@guard
    def logger(self, code, message):
        print("Main.logger:", code, message)


# entry point
def clingo_plus_main_ng():
    clingo.application.clingo_main(Main(), arguments=())


def Noop(next, *args):
    return next(*args)

    
class Error:
    pass
    
    
def default_control(control=None, arguments=(), logger=None, message_limit=20, **etc):
    """ Creates a Control when none is given (when used without clingo_main)."""

    def prepare(next):
        if control:
            return control
        ctrl = next()
        if ctrl:
            return ctrl
        return clingo.Control(arguments=arguments, logger=logger, message_limit=message_limit)

    return prepare, Noop, Noop, Noop


def clingo_default_control(files=(), context=None, yield_=False, parts=(), **etc):
    """ Controller implementing the default Clingo behaviour. """

    def load(next, control):
        for f in files:
            control.load(f)
        if not files:
            control.load("-")
                    
    def ground(next, control):
        control.ground(parts=parts, context=context)
                
    def solve(next, control):
        return control.solve(on_model=None, yield_=yield_)

    return Noop, load, ground, solve

    
def source_support_control(source=None, **etc):
    """ Loads source given as string. """

    def load(next, control):
        if source:
            control.add(source)
        else:
            next(control)

    return Noop, load, Noop, Noop


def ik_wil_logger_afvangen_control(logger, **etc):
    def prepare(next):
        pass
    return Noop, Noop, Noop, Noop


controllers = [ik_wil_logger_afvangen_control,
               default_control,
               source_support_control,
               clingo_default_control]
   
    
def clingo_session(
        source=None,
        files=(),
        arguments=(),          # \   <= Clingo cmdline specifiek
        logger=None,           #  | inputs for making Control
        message_limit=20,      #  |
        control=None,          # /
        parts=(('base', ()),),
        context=None,
        assumptions=(),
        on_model=None,
        on_sat=None,
        on_statistics=None,
        on_finish=None,
        on_core=None,
        on_last=None,
        yield_=False,
        async_=False):

    controller_functions = [
        controller(
            source=source,
            files=files,
            arguments=arguments,
            logger=logger,
            message_limit=message_limit,
            control=control,
            parts=parts,
            context=context,
            yield_=yield_)
        for controller in controllers]

    def call(i, n, *args):
        func = controller_functions[i][n]
        print(f"CALL {i}/{n}: {func.__qualname__}{args}", file=sys.stderr)
        def next(*a):
            if i < len(controller_functions) -1:
                return call(i+1, n, *a)
        return func(next, *args)

    control = call(0, 0)
    call(0, 1, control)
    call(0, 2, control)
    return call(0, 3, control)
        

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
    test.startswith(stdout.getvalue(), 'clingo+ version 5.7.1\nReading from stdin\nSolving...\nAnswer: 1\nowkee\nSATISFIABLE')
    
        
@test
def test_simple():
    result = clingo_session(source="a.")
    test.truth(result.satisfiable)


@test
def test_logger():
    log = []
    def my_log(code, message):
        log.append((code, message))
    with test.raises(RuntimeError, "parsing failed"):
        clingo_session(source='0.', logger=my_log)
    test.eq([(clingo.MessageCode.RuntimeError, '<block>:1:2-3: error: syntax error, unexpected .\n')], log)
