
import clingo

import selftest
test = selftest.get_tester(__name__)


def clingo_control_plugin(next, control=None, **etc):
    """ Provides a default control when there is none. """
    
    def logger(code, message):
        _logger(code, message)
    
    if not control:
        control = clingo.Control(logger=logger) # pass arguments and message_limit
        
    _logger, main = next(control=control, **etc)
        
    return main


@test
def control_plugin_basics():
    trace = []
    def next(control=None, more=None):
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
    def next(control=None):
        trace.append(control)
        return 1, 2
    main = clingo_control_plugin(next, control="ceçi c'est un Control")
    test.eq("ceçi c'est un Control", trace[0])
    test.eq(2, main)
    test.eq(1, len(trace))