
import sys
import clingo


from clingo.script import enable_python
enable_python()


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
        if not files:
            control.load('-')

    def ground(control, **kw):
        control.ground(**kw)

    def solve(control, **kw):
        result = control.solve(**kw)
        # Clingo Python/C++ API does not maintain a relation between a Handle and its Control.
        # As soon as the control goes out of scope, the Handle can no longer work.
        # Therefor we keep the control save by poking it on the handle ourselves.
        result.__control = control # save control from GC.
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


#@test
def no_files():
    import os
    logger, load, ground, solve = clingo_defaults_plugin(None)
    control = clingo.Control()
    os.write(0, b"aap")
    load(control, files=())
    ground(control)
    with solve(control, yield_=True) as s:
        for m in s:
            print(m)
