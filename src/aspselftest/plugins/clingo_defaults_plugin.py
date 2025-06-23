
import sys
import clingo

from .misc import write_file

import selftest
test = selftest.get_tester(__name__)


def clingo_defaults_plugin(next, control=None, **etc):
    """ Implements Clingo sequence with default actions. """
    
    def logger(code, message):
        print(f"UNHANDLED MESSAGE: code={code}, message: {message!r}", file=sys.stderr)
                
    def load(files=()):
        for filename in files:
            control.load(filename)
                    
    return logger, load, control.ground, control.solve
    

@test
def clingo_defaults_plugin_basics(tmp_path, stderr):
    file1 = write_file(tmp_path/'file1.lp', 'a. b.')
    control = clingo.Control()
    _, load, ground, solve = clingo_defaults_plugin(None, control=control)
    load(files=(file1,))
    ground()
    test.eq('a', str(next(control.symbolic_atoms.by_signature('a', 0)).symbol))
    test.eq('b', str(next(control.symbolic_atoms.by_signature('b', 0)).symbol))
    models = []
    solve(on_model=lambda model: models.append(str(model)))
    test.eq(['a b'], models)


@test
def clingo_defaults_plugin_logger(stderr):
    control = clingo.Control()
    logger, l, g, s = clingo_defaults_plugin(None, control=control)
    logger(67, 'message in a bottle')
    test.eq(stderr.getvalue(), "UNHANDLED MESSAGE: code=67, message: 'message in a bottle'\n")


@test
def clingo_defaults_plugin_no_next():
    # Wait and see how this works out when using this plugin as an real plugin with session().
    pass