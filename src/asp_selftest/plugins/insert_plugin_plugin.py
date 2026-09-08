import functools
import importlib
import clingo
from .misc import write_file, is_plugin_instruction
from .clingo_control_plugin import ControlEx

import selftest

test = selftest.get_tester(__name__)


def insert_plugin_plugin(next, **etc):
    next_plugin = next

    def install_plugins(files, control):

        def get_inserts(ast):
            nonlocal next_plugin
            if plugin_name := is_plugin_instruction(ast):
                if ":" in plugin_name:
                    modulename, functionname = plugin_name.rsplit(":", 1)
                else:
                    modulename, functionname = __name__, plugin_name
                module = importlib.import_module(modulename)
                plugin_function = getattr(module, functionname)
                next_plugin = functools.partial(plugin_function, next_plugin)

        control.parse_files(files, callback=get_inserts)
        # clingo.ast.parse_files(files, callback=get_inserts, logger=logger)

        nonlocal _load, _ground, _solve
        _load, _ground, _solve = next_plugin(**etc)

    _load = _ground = _solve = None

    def load(control, files, *a, **k):
        install_plugins(files, control)
        _load(control, files, *a, **k)

    # we just defer the lookup of the functions until the plugin is called
    def ground(*a, **k):
        _ground(*a, **k)

    def solve(*a, **k):
        return _solve(*a, **k)

    return load, ground, solve


def marker_plugin(next, **etc):
    _load, ground, solve = next(**etc)

    def load(control, files):
        _load(control, files)
        control.add("marker.")

    return load, ground, solve


@test
def insert_plugin_basics(tmp_path):
    _trace = []
    trace = _trace.append
    f = write_file(tmp_path / "f.lp", 'insert_plugin("marker_plugin"). main.')

    def next_plugin(**etc):  # no next plugin here b/c testing

        def load(control, files):
            trace(f"load: {files}")
            control.load(files[0])

        def ground(control, parts=(("base", ()),), context=None):
            trace(f"ground: {parts}, {context}")
            control.ground(parts=parts, context=context)

        def solve(control):
            return "next-plugin"

        return load, ground, solve

    load, ground, solve = insert_plugin_plugin(next_plugin)
    control = ControlEx()
    load(control, (f,))
    ground(control)
    test.eq(
        {'insert_plugin("marker_plugin")', "main", "marker"},
        {str(a.symbol) for a in control.symbolic_atoms},
    )
    test.eq(f"load: ({f!r},)", _trace[0])
    test.eq("ground: (('base', ()),), None", _trace[1])
    test.eq(2, len(_trace))
    test.eq("next-plugin", solve(None))


def look_plugin(next, **etc):
    _logger, *rest = next(**etc)

    def logger(code, message):
        _logger(code, "LOOK! " + message)

    return logger, *rest


@test
def fall_back_to_latest_plugin(tmp_path):
    # force parse error; this happens during parsing but the new plugin is
    # added already, so it must use it
    f = write_file(
        tmp_path / "f.lp",
        """\
        insert_plugin("look_plugin").
        parse error.""",
    )
    trace = []

    def next_plugin(**etc):  # no next plugin here b/c testing
        return None, None, None

    load, ground, solve = insert_plugin_plugin(next_plugin)
    with test.raises(SyntaxError, "syntax error, unexpected <IDENTIFIER>"):
        load(ControlEx(), (f,))


# TODO test error conditions (maybe if you really start using this idea)
