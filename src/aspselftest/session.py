import pathlib
import subprocess
import os
import sys
import functools
import enum

import clingo.ast
import selftest

test = selftest.get_tester(__name__)


Handler = enum.IntEnum('Handler', ['LOGGER', 'INIT', 'LOAD', 'GROUND', 'SOLVE'], start=0)


class Main:
    def __init__(self, clingo_session):
        self.clingo_session = clingo_session

    """ Main Application dictated by Clingo, to be fed to clingo_main() """
    program_name = "clingo+"
    message_limit = 20

    def main(self, control, files):
        self.clingo_session(control=control, files=files, logger=self.logger,
                            message_limit=self.message_limit, main=self)

    #@guard
    def logger(self, code, message):
        self._logger(code, message)

        
    def set_logger(self, logger_chain):
        self._logger = logger_chain


def clingo_session_base(main=None, logger=None, plugins=(), source=None, files=(), **kwargs):

    assert plugins, "No plugins."

    def redirect_logger(code, message):
        caller(0, Handler.LOGGER)(code, message)

    if main:
        main.set_logger(redirect_logger)
    if not logger:
        logger = redirect_logger

    handlerssets = [plugin(plugins=plugins, logger=logger, **kwargs) for plugin in plugins]

    def caller(i, h):
        if i >= len(plugins):
            return lambda *a: None
        handler = handlerssets[i][h]
        @functools.wraps(handler)
        def call(*args):
            print(f"call: {handler.__qualname__}({', '.join(map(str,args))})", file=sys.stderr)
            return handler(caller(i+1, h), *args)
        return call

    control = caller(0, Handler.INIT)()
    caller(0, Handler.LOAD)(control, source, files)
    caller(0, Handler.GROUND)(control)
    return control, caller(0, Handler.SOLVE)(control)
        

def test_plugin(**etc):
    def logger(next, code, message):
        pass
    def init(next):
        pass
    def load(next, control):
        pass
    def ground(next, control):
        pass
    def solve(next, control):
        pass
    return logger, init, load, ground, solve


@test
def have_my_own_handler_doing_nothing():
    log = []
    def my_own_handler(logger=None, plugins=(), **etc):
        log.append(etc)
        def logme(*args):
            log.append((*plugins, *args))
            return len(log)
        return logme, logme, logme, logme, logme
    control, result = clingo_session_base(plugins=[my_own_handler], more='here')
    test.eq({'more': 'here'}, log[0])
    test.eq(5, result)
    test.eq([
        (my_own_handler, test.any,),
        (my_own_handler, test.any, 2, None, ()),
        (my_own_handler, test.any, 2),
        (my_own_handler, test.any, 2),
    ], log[1:], diff=test.diff)

        