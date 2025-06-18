import clingo
from .clingoexitcodes import ExitCode
from .misc import write_file

import selftest
test = selftest.get_tester(__name__)


def clingo_main_plugin(next, arguments=(), **etc):
    """ Uses clingo_main() to drive the plugins. It is meant for implementing a Clingo compatible
        main. It does not return anything as to avoid garbage collected C++ objects to ruin the program.
    """
            
    class App:
        """ As per Clingo spec: callbacks main() and logger(). """
        exception = None
                
        def main(self, control, files):
            """ As required by clingo_main. It must not raise. """
            try:
                self._logger, _main = next(control=control, files=files, **etc)  # [3]
                return _main()
            except Exception as e:
                self.exception = e
                    
        def logger(self, code, message):
            """ As required by clingo_main. Forwards to next plugin."""
            self._logger(code, message)

    def main():
        app = App()
        exitcode = clingo.clingo_main(app, arguments)  # [2]
        if app.exception:
            raise app.exception
        return exitcode
            
    return main  #[1]


@test
def raise_errors_in_plugins(stdout):
    def malicious_plugin(**etc):
        return 1, 2, 3
    main = clingo_main_plugin(malicious_plugin, arguments=[])
    with test.raises(ValueError, "too many values to unpack (expected 2)"):
        main()
    test.startswith(stdout.getvalue(), """clingo version 5.7.1
Reading from stdin
UNKNOWN""")


@test
def raise_errors_in_main(stdout):
    def malicious_plugin(**etc):
        def malicious_main():
            1/0
        return None, malicious_main
    main = clingo_main_plugin(malicious_plugin, arguments=[])
    with test.raises(ZeroDivisionError, "division by zero"):
        main()
    test.startswith(stdout.getvalue(), """clingo version 5.7.1
Reading from stdin
UNKNOWN""")


@test
def plugin_basic_noop(stdout):
    arguments = []
    def next(*args, **etc):
        arguments.append(args)
        arguments.append(etc)
        return None, next
    main = clingo_main_plugin(next, arguments=[], etc='42')
    test.eq([], arguments)
    exitcode = main()
    test.eq(ExitCode.UNKNOWN, exitcode)
    test.eq(4, len(arguments))
    plugin_args = arguments[0]
    test.eq((), plugin_args)
    plugin_kwargs = arguments[1]
    test.isinstance(plugin_kwargs['control'], clingo.Control)
    test.eq([], plugin_kwargs['files'])
    test.eq('42', plugin_kwargs['etc'])
    test.eq(3, len(plugin_kwargs))
    main_args = arguments[2:4]
    test.eq([(), {}], main_args)


@test
def pass_arguments_to_files(tmp_path, stdout):
    f1 = write_file(tmp_path/"f1.lp", "f1.")
    f2 = write_file(tmp_path/"f2.lp", "f2.")
    trace = []
    def next_main():
        trace.append('main')
    def next(files=None, **etc):
        trace.append(files)
        trace.append(etc)
        return None, next_main
    main = clingo_main_plugin(next, arguments=[f1, f2])
    main()
    test.eq([f1, f2], trace[0])
    test.isinstance(trace[1]['control'], clingo.Control)
    test.eq('main', trace[2])
    test.eq(3, len(trace))


@test
def forward_logger():
    trace = []
    def next(control=None, files=()):
        def next_main():
            control.add("error")  # trigger call of logger
        def logger(code, message):
            trace.append(message)
        return logger, next_main
    main = clingo_main_plugin(next)
    with test.raises(RuntimeError, "parsing failed"):
        main()
    test.eq('<block>:2:1-2: error: syntax error, unexpected EOF\n', trace[0])