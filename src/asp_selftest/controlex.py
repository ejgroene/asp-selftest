"""ControlEx wraps a clingo.Control and lets every call to it raise an
exception instead of only logging it to a logger function.

The exception gets a detailed trace indicating the exact position where
the given error messages applies (just like Python backtraces).
"""

import clingo.ast
import functools
import selftest
from .messageparser import warn2raise

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

    def new(self, arguments=None):
        """creates a new instance with the same arguments as this one was created"""
        return __class__(
            arguments=arguments or self.arguments,
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
                    assert str(e) in [
                        "parsing failed",
                        "syntax error",
                        "grounding stopped because of errors",
                    ], e
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
