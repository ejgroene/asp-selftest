


from .misc import write_file

import selftest

test = selftest.get_tester(__name__)


def clingo_sequencer_plugin(
        next,
        control=None,
        files=(),
        parts=(('base', ()),),
        context=None,
        on_model=None,
        yield_=False,
        **etc):
    """ Breaks down main into Clingo-specific steps. """
    
    logger, load, ground, solve = next(parts=parts, **etc)
            
    def main():
        load(control, files=files)
        ground(control, parts=parts, context=context)
        return solve(control, on_model=on_model, yield_=yield_)
            
    return logger, main



@test
def sequencer_plugin_basics(tmp_path):

    logs = []
    trace = []

    def next_plugin(logger=None, **etc):
        trace.append(etc)
        def load(control, files=()):
            trace.append(files)
        def ground(control, parts=(('base', ()),), context=None):
            trace.append(parts)
            trace.append(context)
        def solve(control, on_model=None, yield_=False):
            # many more, see https://potassco.org/clingo/python-api/current/clingo/control.html#clingo.control.Control.solve
            trace.append(on_model)
            trace.append(yield_)
        return logger, load, ground, solve

    def my_logger(code, message):
        logs.append((code, message))

    class MyContext:
        def my_func(a):
            return a

    def my_on_model(model):
        pass

    file1 = write_file(tmp_path/'file1.lp', "a(@my_func(b)).")
    logger, main = clingo_sequencer_plugin(
        next_plugin,
        logger=my_logger,
        files=(file1,),
        parts=(('part_a', ()), ('part_b', ())),
        context=MyContext(),
        on_model=my_on_model,
        yield_=True,
        more='better')

    logger(42, "message 42")
    test.eq([(42, "message 42")], logs)

    main()

    test.eq({'parts': (('part_a', ()), ('part_b', ())), 'more': 'better'}, trace[0])
    test.eq((file1,), trace[1])
    test.eq((('part_a', ()), ('part_b', ())), trace[2])
    test.isinstance(trace[3], MyContext)
    test.eq(my_on_model, trace[4])
    test.eq(True, trace[5])


@test
def test_defaults():
    
    trace = []
        
    def next_plugin(logger=None, **etc):
        trace.append(etc)
        def load(control, files='-'):
            trace.append(files)
        def ground(control, parts='-', context='-'):
            trace.append(parts)
            trace.append(context)
        def solve(control, on_model='-', yield_='-'):
            trace.append(on_model)
            trace.append(yield_)
        return logger, load, ground, solve

    #file1 = write_file(tmp_path/'file1.lp', "a(@my_func(b)).")
    logger, main = clingo_sequencer_plugin(next_plugin)

    main()

    test.eq({'parts': (('base', ()),)}, trace[0])
    test.eq((), trace[1])
    test.eq((('base', ()),), trace[2])
    test.eq(None, trace[3])
    test.eq(None, trace[4])
    test.eq(False, trace[5])
