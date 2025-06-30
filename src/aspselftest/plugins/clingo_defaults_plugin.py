
import sys
import clingo

from .misc import write_file

import selftest
test = selftest.get_tester(__name__)


def clingo_defaults_plugin(next, **etc):
    """ Implements Clingo sequence with default actions. """
    
    def logger(code, message):
        print(f"UNHANDLED MESSAGE: code={code}, message: {message!r}", file=sys.stderr)
                
    def load(control, files=()):
        for filename in files:
            control.load(filename)

    def ground(control, **kw):
        control.ground(**kw)

    def solve(control, **kw):
        result = control.solve(**kw)
        result.__control = control # save control from GC. Clingo C++ API does not maintain a relation.
        return result
                    
    return logger, load, ground, solve
    

@test
def clingo_defaults_plugin_basics(tmp_path, stderr):
    file1 = write_file(tmp_path/'file1.lp', 'a. b.')
    control = clingo.Control()
    _, load, ground, solve = clingo_defaults_plugin(None)
    load(control, files=(file1,))
    ground(control)
    test.eq('a', str(next(control.symbolic_atoms.by_signature('a', 0)).symbol))
    test.eq('b', str(next(control.symbolic_atoms.by_signature('b', 0)).symbol))
    models = []
    solve(control, on_model=lambda model: models.append(str(model)))
    test.eq(['a b'], models)


@test
def clingo_defaults_plugin_logger(stderr):
    control = clingo.Control()
    logger, l, g, s = clingo_defaults_plugin(None)
    logger(67, 'message in a bottle')
    test.eq(stderr.getvalue(), "UNHANDLED MESSAGE: code=67, message: 'message in a bottle'\n")


@test
def keep_control_from_GC():
    _, l, g, s = clingo_defaults_plugin(None)
    control = clingo.Control()
    result = s(control)
    test.eq(control, result.__control)


@test
def clingo_defaults_plugin_no_next():
    # Wait and see how this works out when using this plugin as an real plugin with session().
    pass
