
import tempfile
import clingo.ast



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