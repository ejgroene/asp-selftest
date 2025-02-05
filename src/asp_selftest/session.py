
import sys
import clingo


from .delegate import Delegate


class CompoundContext:
    """ Clingo looks up functions in __main__ OR in context; we need both.
        (Functions defined in #script land in __main__)
    """

    def __init__(self, *contexts):
        self._contexts = contexts

    def add_context(self, *context):
        self._contexts += context

    def __getattr__(self, name):
        for c in self._contexts:
            if f := getattr(c, name, None):
                return f
        return getattr(sys.modules['__main__'], name)



class DefaultHandler:

    def parse(self, session):
        session['ast'] = ast = []
        clingo.ast.parse_files(files, callback=ast.append, logger=self.logger, message_limit=1)
        # insert processors here?

    def load(self, session):
        load_ast(session['ast'], session['control'])

    def ground(self, session):
        session['control'].ground(session['parts'], context=session['context'])

    def solve(self, session):
        session['control'].solve(**session['solve_options'])

    def logger(self, code, message):
        print(message)


class AspSession(Delegate):

    delegates = ('parse', 'load', 'ground', 'solve', 'logger')
    delegatees = (DefaultHandler(),)

    def __init__(self, source=None, files=None, control=None):
        assert files or source
        self.session['source'] = source
        self.session['files'] = files
        self.session['control'] = control

    def __call__(self, parts=(('base', ()),), context=CompoundContext(), **solve_options):
        self.session['parts'] = parts
        self.session['context'] = context
        self.session['solve_options'] = solve_options
        self.parse(self.session)
        self.load(self.session)
        self.ground(self.session)
        self.solve(self.session)



