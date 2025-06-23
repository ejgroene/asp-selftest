
import tempfile
import clingo.ast




def clingo_defaults_plugin(next, control=None, **etc):
    """ Implements Clingo sequence with default actions. """
    
    def logger(code, message):
        print("LOG:", code, message)
                
    def load(files=()):
        for filename in files:
            control.load(filename)
                    
    return logger, load, control.ground, control.solve