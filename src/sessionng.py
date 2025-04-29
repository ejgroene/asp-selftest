import pathlib
import subprocess
import os
import sys
import functools
import enum

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


def default_control_handlers(control=None, arguments=(), logger=None, message_limit=20, **etc):
    """ Creates a Control when none is given (when used without clingo_main)."""

    def init(next):
        if control:
            return control
        if ctrl := next():
            return ctrl
        return clingo.Control(arguments=arguments, logger=logger, message_limit=message_limit)

    return init, Noop, Noop, Noop


def clingo_default_handlers(source=None, files=(), parts=(('base', ()),), 
                           arguments=(), logger=None, message_limit=20,
                           control=None, context=None, plugins=(),
                           **solve_options):
    """ Controller implementing the default Clingo behaviour. """

    def init(next):
        return control

    def load(next, control):
        for f in files:
            control.load(f)
        if not files:
            control.load("-")
                    
    def ground(next, control):
        control.ground(parts=parts, context=context)
                
    def solve(next, control):
        return control.solve(**solve_options)

    return init, load, ground, solve

    
def source_support_handlers(source=None, **etc):
    """ Loads source given as string. """

    def load(next, control):
        if source:
            control.add(source)
        else:
            next(control)

    return Noop, load, Noop, Noop


default_plugins = (
    default_control_handlers,
    source_support_handlers,
    clingo_default_handlers
)
   
    
Handler = enum.IntEnum('Handler', ['INIT', 'LOAD', 'GROUND', 'SOLVE'], start=0)


def clingo_session(plugins=default_plugins, **kwargs):
    
    handlerssets = [plugin(plugins=plugins, **kwargs) for plugin in plugins]

    def caller(i, h):
        if i >= len(plugins):
            return Noop
        handler = handlerssets[i][h]
        @functools.wraps(handler)
        def call(*args):
            return handler(caller(i+1, h), *args)
        return call

    control = caller(0, Handler.INIT)()
    caller(0, Handler.LOAD)(control)
    caller(0, Handler.GROUND)(control)
    return caller(0, Handler.SOLVE)(control)
        

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


@test
def have_my_own_handler_doing_nothing():
    log = []
    def my_own_handler(logger=None, plugins=(), **etc):
        def logme(*args):
            log.append((*plugins, *args))
            return len(log)
        return logme, logme, logme, logme
    result = clingo_session(plugins=[my_own_handler])
    test.eq(4, result)
    test.eq([
        (my_own_handler, Noop,),
        (my_own_handler, Noop, 1),
        (my_own_handler, Noop, 1),
        (my_own_handler, Noop, 1),
    ], log)

        