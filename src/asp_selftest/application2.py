
import functools
import contextlib

import clingo
from clingo import Control, Application, clingo_main

from .exceptionguard import GuardExceptions

import selftest
test = selftest.get_tester(__name__)


class MainApp(Application, GuardExceptions):
    """ An instance of this class is the first argument to clingo_main()
        NB: clingo_main does not allow for exceptions being thrown in the
            python code it calls. So we capture all exceptions and raise
            them after clingo_main returned.
    """
    program_name = 'clingo+' # clingo requirement
    message_limit = 1        # idem, 1, so fail fast

    def __init__(self, programs, hooks, arguments):
        self.programs = programs
        self.hooks = hooks
        self.arguments = arguments

    def main(self, ctl, files): # called by clingo's clingo_main
        self.session = AspSession(files=files, control=ctl)
        self.session(parts=[(p,()) for p in self.programs])

    def logger(self, code, message):
        self.session.logger(code, message)


@test
def main_clingo_app(tmp_path):
    f = tmp_path/"f"
    f.write_text("ape.")
    app = MainApp()
    test.isinstance(app, Application)
    with app:
        test.eq('clingo+', app.program_name)
        ctl = Control()
        app.main(ctl, [f.as_posix()]) # signature as expected by clingo_main
        test.eq('ape', find_symbol(ctl, "ape"))
