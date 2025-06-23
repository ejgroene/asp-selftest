
from .messageparser import warn2raise

import selftest
test = selftest.get_tester(__name__)


def msg2exc(code, message):
    return warn2raise(None, None, code, message)


def clingo_syntaxerror_plugin(next, msg2exc=msg2exc, **etc):
    """ Takes clingo log message to raise rich exception."""

    _logger, _main = next(**etc)

    exception = []

    def logger(code, message):
        _logger(code, message)
        rich_exception = msg2exc(code, message)
        exception.append(rich_exception)

    def main():
        try:
            return _main() # expect Clingo to call logger on error
        except RuntimeError as e:
            raise exception.pop()
            
    return logger, main

@test
def syntaxerror_basics():
    
    def next(control=None):
        def next_main():
            control(42, "not good") # fake; but we only want to trigger logger
            raise RuntimeError
        def next_logger(code, message):
            pass
        return next_logger, next_main
        
    # we fake the control and directly pass the logger
    def prime_logger(code, message):
        logger(code, message)
            
    logger, main = clingo_syntaxerror_plugin(next, control=prime_logger, msg2exc=lambda code, msg: SyntaxError(msg))
        
    with test.raises(SyntaxError, "not good"):
        main()

    # TODO somehow test mapping the code/message to a fully specified
    #      SyntaxError separately (mapping code in messageparser.py)
    #      - test passing etc
    #      - test calling next_logger
    # warn2raise(lines, label, code, msg)

