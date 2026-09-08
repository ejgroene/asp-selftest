import clingo
from .misc import write_file, ExitCode
from .clingo_control_plugin import ControlEx

import selftest

test = selftest.get_tester(__name__)


VERSION = ".".join(map(str, clingo.version()))


def clingo_main_plugin(next, arguments=(), **etc):
    """Uses clingo_main() to drive the plugins. It is meant for implementing a Clingo compatible
    main. It does not return anything as to avoid garbage collected C++ objects to ruin the program.
    """

    class App:  # (clingo.Application):
        """As per Clingo spec: callbacks main() and logger()."""

        program_name = "clingo+"
        message_limit = 10
        exceptions = []

        def main(self, control, files):
            """As required by clingo_main. It must not raise."""
            try:
                self.controlex = ControlEx(
                    control=control,
                    arguments=arguments,
                    message_limit=self.message_limit,
                )
                _main = next(control=self.controlex, files=files, **etc)  # [3]
                return _main()  #  [4]
            except Exception as e:
                self.exceptions.append(e)

        def logger(self, code, message):
            """As required by clingo_main. Redirect to controlex."""
            self.controlex.logger(code, message)

    def main():
        app = App()
        exitcode = clingo.clingo_main(app, arguments)  # [2]
        if app.exceptions:
            raise app.exceptions[0]  # we report only the first one
        return exitcode

    return main  # [1]


@test
def clingo_thingies(stdout):
    def next_plugin():
        return None, lambda: None

    clingo_main_plugin(next_plugin, arguments=["--help"])()
    out = stdout.getvalue()
    test.startswith(
        out, "clingo+ version 5.8.0\nusage: clingo+ [number] [options] [files]\n\n"
    )


@test
def raise_errors_in_plugins(stdout):
    def malicious_plugin(**etc):
        return 1, 2, 3

    main = clingo_main_plugin(malicious_plugin)
    with test.raises(TypeError, "'tuple' object is not callable"):
        main()
    test.startswith(
        stdout.getvalue(),
        f"""clingo+ version {VERSION}
Reading from stdin
UNKNOWN""",
    )


@test
def raise_errors_in_main(stdout):
    def malicious_plugin(**etc):
        def malicious_main():
            1 / 0

        return malicious_main

    main = clingo_main_plugin(malicious_plugin, arguments=[])
    with test.raises(ZeroDivisionError, "division by zero"):
        main()
    test.startswith(
        stdout.getvalue(),
        f"""clingo+ version {VERSION}
Reading from stdin
UNKNOWN""",
    )


@test
def plugin_basic_noop(stdout):
    arguments = []

    def next(*args, **etc):
        # !! we test only the plugin; hence we have no 'next' as first argument
        #    when called with session(), we have the next plugin as 'next'.
        arguments.append(args)
        arguments.append(etc)
        return lambda *a: arguments.append(a)

    main = clingo_main_plugin(next, arguments=[], etc="42")
    test.eq([], arguments)
    exitcode = main()
    test.eq(ExitCode.UNKNOWN, exitcode)
    test.eq(3, len(arguments))

    plugin_args = arguments[0]
    test.eq((), plugin_args)

    plugin_kwargs = arguments[1]
    test.isinstance(plugin_kwargs["control"], ControlEx)
    test.eq([], plugin_kwargs["files"])
    test.eq("42", plugin_kwargs["etc"])
    test.eq(3, len(plugin_kwargs))

    main_args = arguments[2:3]
    test.eq([()], main_args)


@test
def pass_arguments_to_files(tmp_path, stdout):
    f1 = write_file(tmp_path / "f1.lp", "f1.")
    f2 = write_file(tmp_path / "f2.lp", "f2.")
    trace = []

    def next_main():
        trace.append("main")

    def next(files=None, **etc):
        trace.append(files)
        trace.append(etc)
        return next_main

    main = clingo_main_plugin(next, arguments=[f1, f2])
    main()
    test.eq([f1, f2], trace[0])
    test.isinstance(trace[1]["control"], ControlEx)
    test.eq("main", trace[2])
    test.eq(3, len(trace))


@test
def forward_logger(stdout):
    trace = []

    def next(logger=None, control=None, files=(), arguments=()):
        def next_main():
            assert isinstance(control, ControlEx), control
            control.add("error")  # trigger call of logger

        return next_main

    main = clingo_main_plugin(next)
    with test.raises(SyntaxError, "syntax error, unexpected EOF"):
        main()


@test
def pass_arguments_to_next_plugin(stdout):
    trace = []

    def next_plugin(control=None, files=()):
        trace[:] = control.arguments
        return lambda: None

    main = clingo_main_plugin(next_plugin, arguments=["--project=no"])
    test.eq([], trace)
    exitcode = main()
    test.eq(0, exitcode)
    test.eq(["--project=no"], trace)
