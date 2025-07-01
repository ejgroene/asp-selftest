import functools
import importlib
import clingo
from .misc import write_file, is_plugin_instruction

import selftest
test = selftest.get_tester(__name__)


def insert_plugin_plugin(next, **etc):
    next_plugin = next

    def install_plugins(files):
        
        def get_inserts(ast):
            nonlocal next_plugin
            if plugin_name := is_plugin_instruction(ast):
                if ':' in plugin_name:
                    modulename, functionname = plugin_name.rsplit(':', 1)
                else:
                    modulename, functionname = __name__, plugin_name
                module = importlib.import_module(modulename)
                plugin_function = getattr(module, functionname)
                next_plugin = functools.partial(plugin_function, next_plugin)
   
        clingo.ast.parse_files(files, callback=get_inserts, logger=logger)

        nonlocal _logger, _load, _ground, _solve
        _logger, _load, _ground, _solve = next_plugin(**etc)

    _logger = _load = _ground = _solve = None

    def logger(*a):
        nonlocal _logger
        if _logger is None:  # plugin not called yet, do it now
            _logger, _, _, _ = next_plugin(**etc)
        _logger(*a)

    def load(control, files, *a, **k):
        install_plugins(files)
        _load(control, files, *a, **k)

    # we just defer the lookup of the functions until the plugin is called
    def ground(*a, **k):
        _ground(*a, **k)
        
    def solve(*a, **k):
        return _solve(*a, **k)

    return logger, load, ground, solve

def marker_plugin(next, **etc):
    logger, _load, ground, solve = next(**etc)
    def load(control, files):
        _load(control, files)
        control.add("marker.")
    return logger, load, ground, solve

@test
def insert_plugin_basics(tmp_path):
    _trace = []
    trace = _trace.append
    f = write_file(tmp_path/'f.lp', 'insert_plugin("marker_plugin"). main.')
    def next_plugin(**etc): # no next plugin here b/c testing
        def logger(code, message):
            trace(f"logger: {code}, {message}")
        def load(control, files):
            trace(f"load: {files}")
            control.load(files[0])
        def ground(control, parts=(('base', ()),), context=None):
            trace(f"ground: {parts}, {context}")
            control.ground(parts=parts, context=context)
        def solve(control):
            return "next-plugin"
        return logger, load, ground, solve
    logger, load, ground, solve = insert_plugin_plugin(next_plugin)
    logger(42, "help!")
    test.eq("logger: 42, help!", _trace[0])
    control = clingo.Control()
    load(control, (f,))
    ground(control)
    test.eq(
        {'insert_plugin("marker_plugin")', 'main', 'marker'},
        {str(a.symbol) for a in control.symbolic_atoms})
    test.eq(f"load: ({f!r},)", _trace[1])
    test.eq("ground: (('base', ()),), None", _trace[2])
    test.eq(3, len(_trace))
    test.eq('next-plugin', solve(None))


def look_plugin(next, **etc):
    _logger, *rest = next(**etc)
    def logger(code, message):
        _logger(code, "LOOK! " + message)
    return logger, *rest


@test
def fall_back_to_latest_plugin(tmp_path):
    # force parse error; this happens during parsing but the new plugin is
    # added already, so it must use it
    f = write_file(tmp_path/'f.lp', """\
        insert_plugin("look_plugin").
        parse error.""")
    trace = []
    def next_plugin(**etc): # no next plugin here b/c testing
        def logger(code, message):
            trace.append((code.value, message))
        return logger, None, None, None
    logger, load, ground, solve = insert_plugin_plugin(next_plugin)
    with test.raises(RuntimeError, "syntax error"):
        load(None, (f,))
    test.eq((1, f"LOOK! {f}:2:15-20: error: syntax error, unexpected <IDENTIFIER>\n"), trace[0])


@test
def use_proper_logger(tmp_path):
    # an parse error occurs before the plugin is inserted
    f = write_file(tmp_path/'f.lp', """\
        parse error.
        insert_plugin("look_plugin").""")
    trace = []
    def next_plugin(**etc): # no next plugin here b/c testing
        def logger(code, message):
            trace.append((code.value, message))
        return logger, None, None, None
    logger, load, ground, solve = insert_plugin_plugin(next_plugin)
    with test.raises(RuntimeError, "syntax error"):
        load(None, (f,))
    test.eq((1, f"{f}:1:15-20: error: syntax error, unexpected <IDENTIFIER>\n"), trace[0])


#TODO test error conditions (maybe if you really start using this idea)
