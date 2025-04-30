import traceback

import selftest
test =  selftest.get_tester(__name__)

from sessionng import clingo_session, default_plugins, Noop, run_clingo_plus_main
from asp_selftest.error_handling import warn2raise


def errorplugin(logger=None, source=None, plugins=(), label='?', **etc):

    errors = []

    def my_logger(next, code, message):
        errors.append((code, message))

    def _raise():
        code, message = errors[-1]
        lines = source.splitlines()
        raise warn2raise(lines, label, code, message)

    def load(next, control):
        try:
            next(control)
        except RuntimeError as e:
            assert str(e) == "parsing failed", e
            assert errors, errors
            _raise()

    def ground(next, control):
        next(control)
        if errors:
            _raise()

    return my_logger, Noop, load, ground, Noop


@test
def simple_load_error():
    with test.raises(SyntaxError) as e:
        clingo_session(source='a', label='src_a', plugins=[errorplugin, *default_plugins])
    test.eq("syntax error, unexpected EOF (src_a, line 2)", str(e.exception))
    test.eq(('syntax error, unexpected EOF', ('src_a', 2, None, '    1 a\n      ^ syntax error, unexpected EOF')),
             e.exception.args)

@test
def simple_ground_error():
    with test.raises(SyntaxError) as e:
        clingo_session(source='a :- b.', label='src_b', plugins=[errorplugin, *default_plugins])
    test.eq('atom does not occur in any rule head:  b (src_b, line 1)', str(e.exception))
    test.eq(('atom does not occur in any rule head:  b',
             ('src_b', 1, None, '    1 a :- b.\n           ^ atom does not occur in any rule head:  b')),
             e.exception.args)