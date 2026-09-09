import selftest

from ..controlex import ControlEx

test = selftest.get_tester(__name__)


def clingo_control_plugin(
    next,
    control=None,
    arguments=[],
    message_limit=10,
    observer=None,
    **etc,
):
    """Provides an (exception raising) default control when there is none."""

    assert not control, control

    if not control:
        control = ControlEx(
            arguments=arguments,
            message_limit=message_limit,
            observer=observer,
        )

    main = next(
        # musn't we pass all arguments given to us?
        control=control,
        **etc,
    )

    assert callable(main), main

    return main


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

    def next_plugin(control=None, **etc):
        trace.append(control)
        return lambda: None

    clingo_control_plugin(next_plugin, message_limit=2)
    control = trace[0]
    test.eq(2, control.message_limit)
    control.add("p :- a.  q :- b.  r :- c.")  # cause 3 messages
    with test.raises(SyntaxError, "atom does not occur in any rule head:  b") as e:
        control.ground()


@test
def pass_yield_and_observer():
    def next(control, yield_=None):
        return lambda: f"yield:{yield_}"

    class Observer:
        pass

    main = clingo_control_plugin(next, observer=Observer(), yield_=True)
    test.eq("yield:True", main())
