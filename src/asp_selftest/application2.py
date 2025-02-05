
class MainApp(Application, contextlib.AbstractContextManager):
    """ An instance of this class is the first argument to clingo_main()
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

    

