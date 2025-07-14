
import tempfile
import pathlib

import selftest
test = selftest.get_tester(__name__)

from .misc import write_tempfile


def source_plugin(next, source=None, label=None, files=(), **etc):
    """ Turns source as string into temporary file. """
    
    source_file = None
            
    if source:
        source_file = write_tempfile(f"-{label or 'string'}.lp", source)
        files = (*files, source_file.name)

    _main = next(files=files, **etc)
    
    def main():
        try:
            return _main()
        finally:
            if source_file:
                source_file.close()
            
    return main


@test
def source_plugin_basics():
    
    trace = []
        
    def next_plugin(files=(), misc=None):
        trace.append(files)
        trace.append(misc)
        def next_main():
            trace.append('next_main')
        return next_main
            
    main = source_plugin(
        next_plugin,
        source="one(1).",
        label='my-logic',
        files=('a.lp',),
        misc='fortytwo')

    test.eq(('a.lp', test.any), trace[0])
    test.eq('fortytwo', trace[1])
    filename = trace[0][1]
    test.endswith(filename, "-my-logic.lp")
    test.truth(pathlib.Path(filename).exists())
    test.eq("one(1).", open(filename).read())
    test.eq(2, len(trace))

    main()
    test.comp.truth(pathlib.Path(filename).exists())
    test.eq('next_main', trace[2])
    test.eq(3, len(trace))


@test
def no_source_given():

    trace = []
        
    def next_plugin(files=(), extra=None):
        trace.append(files)
        trace.append(extra)
        def next_main():
            trace.append('next_main')
            return 42
        return next_main
            
    main = source_plugin(
        next_plugin,
        files=('b.lp',),
        extra='more')

    test.eq(('b.lp',), trace[0])
    test.eq('more', trace[1])
    test.eq(2, len(trace))
    r = main()
    test.eq(42, r)
    test.eq('next_main', trace[2])
    test.eq(3, len(trace))


@test
def avoid_None_as_label():
    trace = []
    def next_plugin(source='no-source', label='no-label', files=()):
        trace.append(source)
        trace.append(label)
        trace.append(files)
    main = source_plugin(next_plugin, source="a.")
    test.eq('no-source', trace[0])
    test.eq('no-label', trace[1])
    test.endswith(trace[2][0], '-string.lp')
