import selftest

test =  selftest.get_tester(__name__)

from sessionng import clingo_session, default_plugins, Noop, run_clingo_plus_main
from asp_selftest.error_handling import warn2raise


def errorplugin(logger=None, source=None, **etc):

    errors = []

    def my_logger(next, code, message):
        errors.append((code, message))

    def load(next, control):
        try:
            next(control)
        except RuntimeError as e:
            assert str(e) == "parsing failed", e
            code, message = errors[-1]
            lines = source.splitlines()
            label = "??"
            raise warn2raise(lines, label, code, message)

    def ground(next, control):
        try:
            next(control)
        except RuntimeError as e:
            assert str(e) == "grounding stopped because of errors", e


    return my_logger, Noop, load, ground, Noop


@test
def simple_syntax_error_with_clingo_main():
    run_clingo_plus_main(b'a')


@test
def simple_syntax_error():
    with test.raises(SyntaxError):
        clingo_session(source='a', plugins=[errorplugin, *default_plugins])
