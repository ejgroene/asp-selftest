import functools
import sys
import clingo
from .messageparser import warn2raise


import selftest

test = selftest.get_tester(__name__)


class ControlEx:
    """Wraps clingo.Control turning logged errors into exceptions."""

    def __init__(self, arguments=(), logger=None, message_limit=20):
        self.arguments = arguments or [
            "--warn",
            "atom-undefined",
            "--warn",
            "operation-undefined",
            "--warn",
            "global-variable",
            "--warn",
            "other",
            "--warn",
            "no-file-included",
        ]
        self.user_logger = logger
        self.message_limit = message_limit
        self.ctrl = clingo.Control(
            arguments=self.arguments,
            logger=self.logger,
            message_limit=self.message_limit,
        )

    def new(self):
        """creates a new instance with the same arguments as this one was created"""
        return __class__(
            arguments=self.arguments,
            logger=self.logger,
            message_limit=self.message_limit,
        )

    def logger(self, code, message):
        self.error = code, message
        if self.user_logger:
            self.user_logger(code, message)

    def __getattr__(self, name):
        attr = getattr(self.ctrl, name)
        if callable(attr):

            @functools.wraps(attr)
            def with_ex(*args, **kwargs):
                try:
                    self.error = None
                    ret = attr(*args, **kwargs)
                except RuntimeError as e:
                    assert str(e) in ["parsing failed"], e
                if self.error:
                    raise warn2raise(None, None, *self.error)
                else:
                    return ret

            return with_ex
        return attr


def clingo_control_plugin(next, control=None, arguments=[], message_limit=20, **etc):
    """Provides a default control when there is none."""

    def logger(code, message):
        _logger(code, message)

    if not control:
        control = clingo.Control(
            logger=logger, arguments=arguments, message_limit=message_limit
        )

    # logger: this is the one passed to Control. That is a fait-accompli!
    #         Use it to build a compatible Control for yourself, if needed.
    #         Please pass it on! Wrap it, if you want, but pass it on.
    # This logger will call the one you return, if not None. Always, since I have no business
    # with it, and it is the *only* way for other plugins to manipulate it.
    # Please return it from your next plugin, wrapped it you want.
    _logger, main = next(
        logger=logger,
        control=control,
        arguments=arguments,
        message_limit=message_limit,
        **etc,
    )

    return main


@test
def control_ex_parse_error():
    c = ControlEx()
    c.add("a.")
    c.ground()
    h = c.solve()
    test.truth(h.satisfiable)
    with test.raises(SyntaxError, "syntax error, unexpected EOF"):
        c.add("b")


@test
def control_ex_ground_error_atom_undefined():
    c = ControlEx()
    c.add("b :- c.")
    with test.raises(SyntaxError, "atom does not occur in any rule head:  c"):
        c.ground()


@test
def control_ex_ground_error_operation_undefined():
    c = ControlEx()
    c.add("b(@f()).")
    with test.raises(SyntaxError, "operation undefined:  function 'f' not found"):
        c.ground()


@test
def pass_kwargs_too():
    c = ControlEx()
    c.add(name="f", parameters=["a"], program="b(2 * a).")
    c.ground(parts=[("f", (clingo.Number(21),))])
    test.eq({"b(42)"}, {str(c.symbol) for c in c.symbolic_atoms})


@test
def identify_wrapped_function_in_exception():
    c = ControlEx()
    f_add = c.add
    # not "ControlEx.__getattr__.<locals>.with_ex"
    test.eq("Control.add", f_add.__qualname__)


@test
def pass_and_store_and_new():
    args = []

    def my_log(code, msg):
        args.append((code, msg))

    c = ControlEx(["--const", "c=42"], my_log, message_limit=1)
    c.add("a :- b(c + 1).")
    with test.raises(SyntaxError, "atom does not occur in any rule head:  b(43)"):
        c.ground()
    test.eq(
        (
            clingo.MessageCode.AtomUndefined,
            "<block>:1:6-14: info: atom does not occur in any rule head:\n  b(43)\n",
        ),
        args[0],
    )
    c1 = c.new()
    c.add("b(43).  a :- b(c + 1).")
    c.ground()
    test.eq({"a", "b(43)"}, {str(c.symbol) for c in c.symbolic_atoms})


@test
def control_plugin_basics():
    trace = []

    def next(control=None, more=None, **etc):
        test.eq("better", more)
        trace.append(control)

        def logger(code, message):
            trace.append(message)

        def main():
            return 43

        return logger, main

    main = clingo_control_plugin(next, more="better")
    control = trace[0]
    test.isinstance(control, clingo.Control)
    test.eq(1, len(trace))
    try:
        control.add("error")
    except RuntimeError:
        pass
    test.eq("<block>:2:1-2: error: syntax error, unexpected EOF\n", trace[1])
    r = main()
    test.eq(43, r)


@test
def control_plugin_makes_no_control_when_given():
    trace = []

    def next(control=None, **etc):
        trace.append(control)
        return 1, 2

    main = clingo_control_plugin(next, control="ceçi c'est un Control")
    test.eq("ceçi c'est un Control", trace[0])
    test.eq(2, main)
    test.eq(1, len(trace))


@test
def pass_arguments_to_control():
    trace = []

    def next_plugin(control=None, arguments=(), **etc):
        trace.append(control)
        trace.append(arguments)

        def logger(code, message):
            trace.append(message)

        return logger, lambda: None

    clingo_control_plugin(next_plugin, arguments=["--const", "a=42"])
    test.eq([test.any, ["--const", "a=42"]], trace)
    control = trace[0]
    control.add("b(a * 2).")
    control.ground()
    test.eq([test.any, ["--const", "a=42"]], trace)
    b = next(control.symbolic_atoms.by_signature("b", 1))
    test.eq("b(84)", str(b.symbol))


@test
def pass_arguments_to_control():
    trace = []
    logs = []

    def next_plugin(control=None, message_limit=20, **etc):
        trace.append(control)
        trace.append(message_limit)

        def logger(code, message):
            logs.append(message)

        return logger, lambda: None

    clingo_control_plugin(next_plugin, message_limit=2)
    test.eq([test.any, 2], trace)
    control = trace[0]
    control.add("p :- a.  q :- b.  r :- c.")  # cause 3 messages
    control.ground()
    test.eq(
        [  # only 2 get logged
            "<block>:1:6-7: info: atom does not occur in any rule head:\n  a\n",
            "<block>:1:15-16: info: atom does not occur in any rule head:\n  b\n",
        ],
        logs,
    )
