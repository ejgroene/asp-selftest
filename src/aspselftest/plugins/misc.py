
import clingo


NA = clingo.String("N/A")


def Noop(next, *args, **kwargs):
    return next(*args, **kwargs)

