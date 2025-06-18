
import tempfile
import clingo.ast


def source_plugin(next, source=None, label='string', files=(), **etc):
    """ Turns source as string into temporary file. """
    
    source_file = None
            
    if source:
        source_file = tempfile.NamedTemporaryFile('w', suffix=f"-{label}.lp") 
        source_file.write(source)
        source_file.flush()
        files = (*files, source_file.name)

    _main = next(files=files, **etc)
    
    def main():
        try:
            return _main()
        finally:
            if source_file:
                source_file.close()
            
    return main


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



def clingo_main_plugin(next, arguments=(), **etc):
    """ Uses clingo_main() to drive the plugins. It is meant for implementing a Clingo compatible
        main. It does not return anything as to avoid garbage collected C++ objects to ruin the program.
    """
            
    class App:
        """ As per Clingo spec: callbacks main() and logger(). """
        exception = None
                
        def main(self, control, files):
            """ As required by clingo_main. It must not raise. """
            self._logger, _main = next(control=control, files=files, **etc)  # [3]
            try:
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