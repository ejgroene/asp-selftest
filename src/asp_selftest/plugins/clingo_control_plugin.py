import functools
import sys
import clingo.ast
from .messageparser import warn2raise


import selftest

test = selftest.get_tester(__name__)


class ControlEx:
    """Wraps clingo.Control turning logged errors into exceptions."""

    def __init__(
        self, arguments=(), logger=None, message_limit=20, control=None, observer=None
    ):
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
        self.observer = observer
        if control:
            self.control = control
        else:
            self.control = clingo.Control(
                arguments=self.arguments,
                logger=self.logger,
                message_limit=self.message_limit,
            )
        if observer:
            self.control.register_observer(observer)  # TODO test in new
        self.parse_files = self._getattr(self, "_parse_files")

    def new(self):
        """creates a new instance with the same arguments as this one was created"""
        return __class__(
            arguments=self.arguments,
            logger=self.logger,
            message_limit=self.message_limit,
        )

    def logger(self, code, message):
        if code != clingo.MessageCode.FileIncluded:
            self.error = code, message
        if self.user_logger:
            self.user_logger(code, message)

    def _getattr(self, obj, name):
        attr = getattr(obj, name)
        if callable(attr):

            @functools.wraps(attr)
            def with_ex(*args, **kwargs):
                try:
                    self.error = None
                    ret = attr(*args, **kwargs)
                except RuntimeError as e:
                    assert str(e) in ["parsing failed", "syntax error"], e
                if self.error:
                    raise warn2raise(None, None, *self.error)
                else:
                    return ret

            return with_ex
        return attr

    def __getattr__(self, name):
        return self._getattr(self.control, name)

    def _parse_files(self, files, callback):
        clingo.ast.parse_files(
            [str(f) for f in files],
            callback=callback,
            logger=self.logger,
            message_limit=self.message_limit,
        )


def clingo_control_plugin(
    next,
    control=None,
    logger=None,
    arguments=[],
    message_limit=20,
    observer=None,
    **etc,
):
    """Provides an (exception raising) default control when there is none."""

    assert not control, control

    if not control:
        control = ControlEx(
            arguments=arguments,
            logger=logger,
            message_limit=message_limit,
            observer=observer,
        )

    main = next(
        control=control,
        **etc,
    )

    assert callable(main), main

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
def control_already_provided():
    msg = []

    def mylogger(*args):
        msg.extend(args)

    myarguments = ["--const", "a=42"]
    ctrl = clingo.Control(arguments=myarguments, logger=mylogger)
    c = ControlEx(control=ctrl, arguments=myarguments, logger=mylogger)
    # There is no way to verify if the control has indeed bee created using
    # the given arguments and logger. We must trust the caller.
    test.eq(ctrl, c.control)
    test.eq(myarguments, c.arguments)
    c.logger("hi", "john")
    test.eq(["hi", "john"], msg)


@test
def parse_files_piggybacks_on_ControlEx(tmp_path):
    f = tmp_path / "f.lp"
    f.write_text("a :- b.")
    c = ControlEx()

    nodes = []

    def callback(node):
        nodes.append(node)

    c.parse_files((f,), callback=callback)
    test.eq(["#program base.", "a :- b."], [str(n) for n in nodes])


@test
def parse_files_gives_same_errors(tmp_path):
    f = tmp_path / "f.lp"
    f.write_text("a")
    c = ControlEx()
    with test.raises(SyntaxError, "syntax error, unexpected EOF"):
        c.parse_files((f,), callback=lambda _: None)


@test
def control_plugin_basics():
    trace = []

    def next(control=None, more=None, **etc):
        test.eq("better", more)
        trace.append(control)

        def main():
            return 43

        return main

    main = clingo_control_plugin(next, more="better")
    control = trace[0]
    test.isinstance(control, ControlEx)
    test.eq(1, len(trace))
    try:
        control.add("error")
    except SyntaxError as e:
        test.eq("syntax error, unexpected EOF (<asp code>, line 2)", str(e))
    r = main()
    test.eq(43, r)


@test
def pass_arguments_to_control1():
    trace = []

    def next_plugin(control=None, arguments=(), **etc):
        trace.append(control)
        trace.append(arguments)

        return lambda: 42

    clingo_control_plugin(next_plugin, arguments=["--const", "a=42"])
    control = trace[0]
    test.eq(["--const", "a=42"], control.arguments)
    control.add("b(a * 2).")
    control.ground()
    b = next(control.symbolic_atoms.by_signature("b", 1))
    test.eq("b(84)", str(b.symbol))


@test
def pass_arguments_to_control2():
    trace = []
    logs = []

    def next_plugin(control=None, **etc):
        trace.append(control)
        return lambda: None

    def user_logger(code, message):
        logs.append(message)

    clingo_control_plugin(next_plugin, logger=user_logger, message_limit=2)
    control = trace[0]
    test.eq(2, control.message_limit)
    control.add("p :- a.  q :- b.  r :- c.")  # cause 3 messages
    with test.raises(SyntaxError, "atom does not occur in any rule head:  b") as e:
        control.ground()
    test.eq(
        [  # only 2 get logged
            "<block>:1:6-7: info: atom does not occur in any rule head:\n  a\n",
            "<block>:1:15-16: info: atom does not occur in any rule head:\n  b\n",
        ],
        logs,
    )


@test
def pass_yield_and_observer():
    def next(control, yield_=None):
        return lambda: f"yield:{yield_}"

    class Observer:
        pass

    main = clingo_control_plugin(next, observer=Observer(), yield_=True)
    test.eq("yield:True", main())
