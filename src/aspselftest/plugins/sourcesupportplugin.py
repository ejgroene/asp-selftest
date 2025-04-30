
import sys
import tempfile
import pathlib

from .misc import Noop


def sourcesupport_plugin(source=None, label=None, **etc):
    """ Loads source given as string. """

    tmpfiles = [None, None]

    def load(next, control, source, files):
        if source:
            tmpfiles[0] = tempfile.NamedTemporaryFile('w', suffix=f"-{label}.lp") 
            tmpfiles[0].write(source)
            tmpfiles[0].flush()
            files = (tmpfiles[0].name, *files)
        if not files:
            tmpfiles[1] = tempfile.NamedTemporaryFile('w', suffix=f"-stdin.lp")
            tmpfiles[1].write(sys.stdin.read())
            tmpfiles[1].flush()
            files = (tmpfiles[1].name, *files)
        next(control, None, files)

                    

    return Noop, Noop, load, Noop, Noop

    