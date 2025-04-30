import pathlib
import subprocess
import os
import sys
import functools
import enum

import clingo.ast
import selftest

test = selftest.get_tester(__name__)


from asp_selftest.utils import is_processor_predicate as is_predicate


class Main:
    """ Main Application dictated by Clingo, to be fed to clingo_main() """
    program_name = "clingo+"
    message_limit = 20

    def main(self, control, files):
        clingo_session(control=control, files=files, logger=self.logger,
                       message_limit=self.message_limit, main=self)

    #@guard
    def logger(self, code, message):
        self._logger(code, message)

        
    def set_logger(self, logger_chain):
        self._logger = logger_chain


def default_control_handlers(control=None, arguments=(), logger=None, message_limit=20, **etc):
    """ Creates a Control when no one else does."""

    def init(next):
        if control := next():
            return control
        return clingo.Control(arguments=arguments, logger=logger, message_limit=message_limit)

    return Noop, init, Noop, Noop, Noop


def clingo_default_handlers(source=None, files=(), parts=(('base', ()),), 
                           arguments=(), logger=None, message_limit=20,
                           control=None, context=None, plugins=(), label=None,
                           **solve_options):
    """ Controller implementing the default Clingo behaviour. """

    def logger(next, code, message):
        #print("DEFAULT.logger:", code, message, file=sys.stderr)
        pass

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

    return logger, init, load, ground, solve

    
def source_support_handlers(source=None, **etc):
    """ Loads source given as string. """

    def load(next, control):
        if source:
            control.add(source)
        else:
            next(control)

    return Noop, Noop, load, Noop, Noop


default_plugins = (
    default_control_handlers,
    source_support_handlers,
    clingo_default_handlers
)
   
    
Handler = enum.IntEnum('Handler', ['LOGGER', 'INIT', 'LOAD', 'GROUND', 'SOLVE'], start=0)


def clingo_session(plugins=default_plugins, main=None, logger=None, **kwargs):

    def redirect_logger(code, message):
        caller(0, Handler.LOGGER)(code, message)

    if main:
        main.set_logger(redirect_logger)
    if not logger:
        logger = redirect_logger

    handlerssets = [plugin(plugins=plugins, logger=logger, **kwargs) for plugin in plugins]

    def caller(i, h):
        if i >= len(plugins):
            return Noop
        handler = handlerssets[i][h]
        @functools.wraps(handler)
        def call(*args):
            #print(f"call: {handler.__qualname__}", file=sys.stderr)
            return handler(caller(i+1, h), *args)
        return call

    control = caller(0, Handler.INIT)()
    caller(0, Handler.LOAD)(control)
    caller(0, Handler.GROUND)(control)
    return control, caller(0, Handler.SOLVE)(control)
        

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
        
def Noop(next, *args, **kwargs):
    return next(*args, **kwargs)


@test
def from_clingo_main(stdout):
    run_clingo_plus_main(b"owkee. #program test_owkee(base).")
    test.startswith(stdout.getvalue(), 'clingo+ version 5.7.1\nReading from stdin\nSolving...\nAnswer: 1\nowkee\nSATISFIABLE')
    
        
@test
def test_simple():
    control, result = clingo_session(source="a.")
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
        log.append(etc)
        def logme(*args):
            log.append((*plugins, *args))
            return len(log)
        return logme, logme, logme, logme, logme
    control, result = clingo_session(plugins=[my_own_handler], more='here')
    test.eq({'more': 'here'}, log[0])
    test.eq(5, result)
    test.eq([
        (my_own_handler, Noop,),
        (my_own_handler, Noop, 2),
        (my_own_handler, Noop, 2),
        (my_own_handler, Noop, 2),
    ], log[1:])

        
@test
def some_parts(stdout):
    """ this test mainly shows that control must be kept alive """
    control, handle = clingo_session(
            source='a. #program test_a(base). cannot(a).',
            parts=[('base', ()), ('test_a', (clingo.Number(42),))],
            yield_=True)
    with handle:
        result = handle.get()
        test.truth(result.satisfiable)
        test.eq("a cannot(a)", str(handle.model()))