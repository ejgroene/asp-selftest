
from clingo import Application, clingo_main


from .exceptionguard import ExceptionGuard
from .session import AspSession
from .error_handling import AspSyntaxError


import selftest
test = selftest.get_tester(__name__)


class MainApp(Application, ExceptionGuard):
    """ An instance of this class is the first argument to clingo_main()
        NB: clingo_main does not allow for exceptions being thrown in the
            python code it calls. So we capture all exceptions and raise
            them after clingo_main returned.
    """
    program_name = 'clingo+' # clingo requirement
    message_limit = 1        # idem, 1, so fail fast

    def __init__(self, programs=None, handlers=(), arguments=()):
        self.programs = programs
        self.handlers = handlers
        self.arguments = arguments

    @ExceptionGuard.guard
    def main(self, ctl, files): # called by clingo's clingo_main
        self.session = AspSession(files=files, handlers=self.handlers)
        with self.session as s:
            return list(s(control=ctl))

    @ExceptionGuard.guard
    def logger(self, code, message):
        self.session.logger(code, message)


@test
def main_clingo_app(tmp_path, stdout):
    logic = tmp_path/"logic.lp"
    logic.write_text("ape.")
    with MainApp() as app:
        test.isinstance(app, Application)
        test.eq('clingo+', app.program_name)
        clingo_main(app, [logic.as_posix()])
    response = stdout.getvalue()
    test.startswith(response, "clingo+ version 5.7.1\nReading from")
    test.contains(response, "Answer: 1\nape\nSATISFIABLE")


# to be called from entry point in __main__
def main_clingo_plus(arguments):
    #with MainApp(hook=[TestRunner(), SyntaxErrors()]) as app:
    from .syntaxerrorhandler import SyntaxErrorHandler
    with MainApp(handlers=[SyntaxErrorHandler()]) as app:
        clingo_main(app, arguments)


@test
def handle_program_args(tmp_path, stdout):
    code = tmp_path/"code.lp"
    code.write_text('appelmoes(yes).')
    main_clingo_plus(['--const', 'yes=lekker', code.as_posix()])
    test.contains(stdout.getvalue(), "Answer: 1\nappelmoes(lekker)")


@test
def add_default_handlers(tmp_path, stdout):
    code = tmp_path/"code.lp"
    code.write_text('failure(2)).')
    with test.raises(AspSyntaxError) as e:
        main_clingo_plus([code.as_posix()])
    test.eq(e.exception.filename, code.as_posix())
    test.endswith(e.exception.text, "   1 failure(2)).\n                ^ syntax error, unexpected )")


@test
def pass_arguments_to_session():
    pass
