

def clingodefault_plugin(source=None, files=(), parts=(('base', ()),), 
                         arguments=(), logger=None, message_limit=20,
                         control=None, context=None, plugins=(), label=None,
                         **solve_options):
    """ Controller implementing the default Clingo behaviour. """

    def logger(next, code, message):
        print("DEFAULT.logger:", code, message, file=sys.stderr)

    def init(next):
        return control

    def load(next, control, source, files):
        assert not source
        assert files
        for f in files:
            control.load(f)
                    
    def ground(next, control):
        control.ground(parts=parts, context=context)
                
    def solve(next, control):
        return control.solve(**solve_options)

    return logger, init, load, ground, solve
