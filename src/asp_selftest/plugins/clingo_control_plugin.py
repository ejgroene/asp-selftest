
import sys
import clingo

import selftest
test = selftest.get_tester(__name__)


def clingo_control_plugin(next, control=None, arguments=[], message_limit=20, **etc):
    """ Provides a default control when there is none. """
    
    def logger(code, message):
        _logger(code, message)
    
    if not control:
        control = clingo.Control(logger=logger, arguments=arguments, message_limit=message_limit)
        
    _logger, main = next(logger=logger, control=control, arguments=arguments, message_limit=message_limit, **etc)
        
    return main


@test
def control_plugin_basics():
    trace = []
    def next(control=None, more=None, **etc):
        test.eq('better', more)
        trace.append(control)
        def logger(code, message):
            trace.append(message)
        def main():
            return 43
        return logger, main
    main = clingo_control_plugin(next, more='better')
    control = trace[0]
    test.isinstance(control, clingo.Control)
    test.eq(1, len(trace))
    try:
        control.add("error")
    except RuntimeError:
        pass
    test.eq('<block>:2:1-2: error: syntax error, unexpected EOF\n', trace[1])
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
    clingo_control_plugin(next_plugin, arguments=['--const', 'a=42'])
    test.eq([test.any, ['--const', 'a=42']], trace)
    control = trace[0]
    control.add("b(a * 2).")
    control.ground()
    test.eq([test.any, ['--const', 'a=42']], trace)
    b = next(control.symbolic_atoms.by_signature('b', 1))
    test.eq('b(84)', str(b.symbol))


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
    test.eq([                                 # only 2 get logged
        '<block>:1:6-7: info: atom does not occur in any rule head:\n  a\n',
        '<block>:1:15-16: info: atom does not occur in any rule head:\n  b\n'],
        logs)
