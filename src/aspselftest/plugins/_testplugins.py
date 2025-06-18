
import tempfile
import clingo.ast



def clingo_control_plugin(next, control=None, **etc):
    """ Provides a default control when there is none. """
    
    def logger(code, message):
        _logger(code, message)
    
    if not control:
        control = clingo.Control(logger=logger)

    _logger, main = next(control=control, **etc)
        
    return main


def clingo_message_to_error_plugin(next, **etc):
    """ Takes clingo log message to raise rich exception."""

    _logger, _main = next(**etc)

    exception = []

    def logger(code, message):
        _logger(code, message)
        exception.append(SyntaxError(message))

    def main():
        try:
            return _main()
        except RuntimeError as e:
            raise exception.pop()
            
    return logger, main


def clingo_sequencer_plugin(next, **etc):
    """ Breaks down main into Clingo-specific steps. """
    
    logger, load, ground, solve = next(**etc)
    get = etc.get
            
    def main():
        load(files=get('files', ()))
        ground(parts=get('parts', (('base', ()),)), context=get('context'))
        return solve(yield_=get('yield_'))
            
    return logger, main


def clingo_defaults_plugin(next, control=None, **etc):
    """ Implements Clingo sequence with default actions. """
    
    def logger(code, message):
        print("LOG:", code, message)
                
    def load(files=()):
        for filename in files:
            control.load(filename)
                    
    return logger, load, control.ground, control.solve