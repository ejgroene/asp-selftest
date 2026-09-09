import sys
import os
import clingo
import selftest
from clingo.script import enable_python

from .misc import write_file

enable_python()
test = selftest.get_tester(__name__)


def clingo_defaults_plugin(next, **etc):
    """Implements Clingo sequence with default actions."""

    def load(control, files=()):
        for filename in files:
            control.load(filename)
        if not files:
            control.load("-")

    def ground(control, **kw):
        control.ground(**kw)

    def solve(control, **kw):
        result = control.solve(**kw)
        # Clingo Python/C++ API does not maintain a relation between a Handle and its Control.
        # As soon as the control goes out of scope, the Handle can no longer work.
        # Therefor we keep the control save by poking it on the handle ourselves.
        result.__control = control  # save control from GC.
        return result

    return load, ground, solve


@test
def clingo_defaults_plugin_basics(tmp_path, stderr):
    file1 = write_file(tmp_path / "file1.lp", "a. b.")
    control = clingo.Control()
    load, ground, solve = clingo_defaults_plugin(None)
    load(control, files=(file1,))
    ground(control)
    test.eq("a", str(next(control.symbolic_atoms.by_signature("a", 0)).symbol))
    test.eq("b", str(next(control.symbolic_atoms.by_signature("b", 0)).symbol))
    models = []
    solve(control, on_model=lambda model: models.append(str(model)))
    test.eq(["a b"], models)


@test
def keep_control_from_GC():
    l, g, s = clingo_defaults_plugin(None)
    control = clingo.Control()
    result = s(control)
    test.eq(control, result.__control)


@test
def no_files_read_from_stdin(tmp_path):
    load, ground, solve = clingo_defaults_plugin(None)
    control = clingo.Control()
    results = []
    # Clingo used libc to read from stdin. It takes some fiddling to
    # put something stdin for libc.
    org_stdin = os.dup(0)
    tmp_stdin = tmp_path / "tmp_stdin"
    tmp_stdin.write_text("a. b.")
    with tmp_stdin.open() as stdin:
        try:
            os.dup2(stdin.fileno(), 0)  # dup our file to stdin (0)
            load(control, files=())
            ground(control)
            with solve(control, yield_=True) as s:
                for m in s:
                    results.extend(map(str, m.symbols(atoms=True)))
        finally:
            os.dup2(org_stdin, 0)
            stdin.close()
    test.eq(["a", "b"], results)
