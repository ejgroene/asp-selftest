import sys
import os
import tempfile
import collections
import itertools
import clingo.ast

import selftest
test =  selftest.get_tester(__name__)

from .misc import NA, write_file, format_symbols


def is_testprogram(a):
    if a.ast_type == clingo.ast.ASTType.Program:
        if a.name.startswith('test_'):
            return a.name, [p.name for p in a.parameters]


def gather_tests(files, logger):
    all_tests = collections.defaultdict(dict)

    def _filter_program(ast):
        filename = ast.location.begin.filename
        tests = all_tests[filename]
        if program := is_testprogram(ast):
            name, dependencies = program
            if name in tests:
                raise AssertionError(f"Duplicate test: {name!r} in {filename}.")
            tests[name] = (dependencies, ast.location.begin.line)

    def _logger(code, message):
        if code != clingo.MessageCode.FileIncluded:
            logger(code, message)
    clingo.ast.parse_files(files, callback=_filter_program, logger=_logger)
    return reversed(all_tests.items())


def testrunner_plugin(next, run_tests=True, logger=None, arguments=(), context=None, **etc):
    """ Runs all tests in every file separately, during loading. """

    next_logger, _load, ground, solve = next(
        logger=logger,
        arguments=arguments,
        context=context,
        **etc)

    def load(control, files):
        stdin_tmp_file_name = None
        if not files:
            asp_code = open(os.dup(0)).read()  # read from stdin without removing the data  #TODO REMOVE
            stdin_data = tempfile.NamedTemporaryFile('w', suffix='-stdin.lp')
            print(asp_code, file=stdin_data, flush=True)
            stdin_tmp_file_name = stdin_data.name
            files = [stdin_tmp_file_name]
        for filename, tests in gather_tests(files, logger):
            print("Testing", 'stdin' if filename.endswith('-stdin.lp') else filename)
            tests_per_file = [('base', ((), 1)), *tests.items()]
                        
            for testname, (dependencies, lineno) in tests_per_file:
                fulltestname = f"{testname}({', '.join(dependencies)})"
                parts = [(testname, [NA for _ in dependencies]), *((d, []) for d in dependencies)]
                print(" ", fulltestname, end='', flush=True)

                try:
                    new_args=list(itertools.dropwhile(lambda p: not p.startswith('--'), arguments))
                    sub_logger, sub_load, sub_ground, sub_solve = next(logger=logger, arguments=new_args, context=context, **etc)
                    sub_control = clingo.Control(
                        arguments=new_args,
                        logger=logger)

                    sub_load(sub_control, files=(filename,))
                    sub_ground(sub_control, parts=parts, context=context)

                    with sub_solve(sub_control, yield_=True) as models:
                        for model in models:
                            if failures := list(model.context.symbolic_atoms.by_signature('cannot', 1)):
                                e = AssertionError(', '.join(str(f.symbol) for f in failures))
                                e.add_note(f"File {filename}, line {lineno}, in {fulltestname}.")
                                e.add_note("Model:\n" + format_symbols(s for s in model.symbols(shown=True) if s.name != 'cannot'))
                                raise e
                finally:
                    print(flush=True)

        _load(control, files)

    return next_logger, load if run_tests else _load, ground, solve


def tracing_clingo_plugin(trace=lambda x: None):
    def tracer(**etc):
        trace(etc)
        def load(control, files):
            trace((control, files))
            control.load(files[0])
        def ground(control, parts, context=None):
            trace((control, parts, context))
            control.ground(parts=parts, context=context)
        def solve(control, yield_):
            trace(yield_)
            return control.solve(yield_=yield_)
        return None, load, ground, solve
    return tracer


@test
def testrunner_plugin_basics(tmp_path, stdout):
    testfile = write_file(tmp_path/'testfile.lp', """\
        #program test_a.
        cannot("I fail").
    """)

    _0, load, ground, solve = testrunner_plugin(tracing_clingo_plugin())

    main_control = clingo.Control()
    with test.raises(AssertionError, 'cannot("I fail")') as e:
        load(main_control, files=(testfile,))
    test.eq(e.exception.__notes__[0], f"File {testfile}, line 1, in test_a().")
    test.eq(stdout.getvalue(), f"Testing {testfile}\n  base()\n  test_a()\n")


@test
def testrunner_plugin_no_failures(tmp_path, stdout):
    testfile = write_file(tmp_path/'testfile.lp', """\
        a.
        #program test_a(base).
        cannot(a) :- not a.
    """)

    _, load, ground, solve = testrunner_plugin(tracing_clingo_plugin())

    main_control = clingo.Control()
    load(main_control, files=(testfile,))
    test.eq(stdout.getvalue(), f"Testing {testfile}\n  base()\n  test_a(base)\n")

    ground(main_control, parts=(('base', ()), ('test_a', ())))
    test.eq('a', str(next(main_control.symbolic_atoms.by_signature('a', 0)).symbol))


@test
def run_tests_per_included_file_separately(tmp_path, stdout, stderr):
    part_a = write_file(tmp_path/'part_a.lp',
        f'#program test_a.')
    part_b = write_file(tmp_path/'part_b.lp',
        f'#include "{part_a}".  #program test_b.')
    part_c = write_file(tmp_path/'part_c.lp',
        f'#include "{part_b}".  #include "{part_a}".  #program test_c.')

    _, load, ground, solve = testrunner_plugin(tracing_clingo_plugin(), arguments=['--warn', 'no-file-included'])
    main_control = clingo.Control(arguments=['--warn', 'no-file-included'])
    load(main_control, files=(part_c,))
    test.eq('', stderr.getvalue())
    out = stdout.getvalue()
    test.contains(out, f"""\
Testing {part_b}
  base()
  test_b()
Testing {part_a}
  base()
  test_a()
Testing {part_c}
  base()
  test_c()""")


# TEST taken from runasptests.py


def parse_and_run_tests(asp_code, trace=lambda _:None, **etc):
    with test.tmp_path as p:
        inputfile = write_file(p/'inputfile.lp', asp_code)
        _, load, _, _ = testrunner_plugin(
            tracing_clingo_plugin(trace=trace), **etc)
        main_control = clingo.Control()
        load(main_control, files=(inputfile,))
    

@test
def cannot_in_base(stdout):
    with test.raises(AssertionError, 'cannot(fail)'):
        parse_and_run_tests("cannot(fail).")  # constraints in base
    test.endswith(stdout.getvalue(), "/inputfile.lp\n  base()\n")
    

@test
def use_arguments_for_testing(stdout):
    trace = []
    asp_program = "sum(a). cannot(a) :- not sum(42)."
    parse_and_run_tests(
        asp_program,
        arguments=['--const', 'a=42'],
        trace=trace.append)
    test.eq({'logger': None, 'arguments': ['--const', 'a=42'], 'context': None}, trace[0])
    with test.raises(AssertionError, "cannot(99)"):
        parse_and_run_tests(
            asp_program,
            arguments=['--const', 'a=99'])
    test.endswith(stdout.getvalue(), "/inputfile.lp\n  base()\n")



@test
def use_context_when_running_tests(stdout):
    trace = []
    asp_program = "#program test_a_42. a(42). cannot(@a()) :- a(@a())."
    n = 43
    class MyContext:
        def a(self):
            return clingo.Number(n)
    mycontext = MyContext()
    parse_and_run_tests(
        asp_program,
        context=mycontext,
        trace=trace.append)
    test.eq(mycontext, trace[0]['context'])
    n = 42
    with test.raises(AssertionError, "cannot(42)"):
        parse_and_run_tests(
            asp_program,
            context=MyContext())
    test.endswith(stdout.getvalue(), "/inputfile.lp\n  base()\n  test_a_42()\n")
    
        
@test
def check_for_duplicate_test():
    with test.raises(Exception) as e:
        parse_and_run_tests(""" #program test_a. \n #program test_a. """)
    test.startswith(str(e.exception), "Duplicate test: 'test_a' in ")


@test
def format_empty_model(stderr, stdout):
    with test.raises(AssertionError) as e:
        parse_and_run_tests("""
            #program test_model_formatting.
            #external what.
            cannot(test) :- not what.
        """)
    msg = str(e.exception)
    #test.eq(msg, f"""MODEL:
    #<empty>
    #Failures in <string>, #program test_model_formatting():
    #cannot(test)
    #""")
    notes = e.exception.__notes__
    test.startswith(notes[0], "File ")
    test.endswith(notes[0], ", line 2, in test_model_formatting().")
    test.eq(notes[1], "Model:\n<empty>")


@test
def format_model_small(stderr, stdout):
    import unittest.mock as mock
    with mock.patch("shutil.get_terminal_size", lambda _: (37,20)):
        with test.raises(AssertionError) as e:
            parse_and_run_tests("""
                #program test_model_formatting.
                this_is_a_fact(1..2).
                #external what.
                cannot(test) :- not what.
            """)
    notes = e.exception.__notes__
    test.startswith(notes[0], "File ")
    test.endswith(notes[0], ", line 2, in test_model_formatting().")
    test.eq(notes[1], """Model:
this_is_a_fact(1)
this_is_a_fact(2)""")


@test
def format_model_wide(stderr, stdout):
    import unittest.mock as mock
    with mock.patch("shutil.get_terminal_size", lambda _: (50,20)):
        with test.raises(AssertionError) as e:
            parse_and_run_tests("""
                #program test_model_formatting.
                this_is_a_fact(1..3).
                #external what.
                cannot(test) :- not what.
            """)
    notes = e.exception.__notes__
    test.startswith(notes[0], "File ")
    test.endswith(notes[0], ", line 2, in test_model_formatting().")
    test.eq(notes[1], """Model:
this_is_a_fact(1)  this_is_a_fact(2)
this_is_a_fact(3)""")


@test
def we_CAN_NOT_i_repeat_NOT_reuse_control():
    c = clingo.Control()
    c.add("a. #program p1. p(1). #program p2. p(2).")
    c.ground()
    test.eq(['a'], [str(s.symbol) for s in c.symbolic_atoms])
    c.cleanup()
    c.ground((('base', ()), ('p1', ())))
    test.eq(['a', 'p(1)'], [str(s.symbol) for s in c.symbolic_atoms])
    c.cleanup()
    c.ground((('base', ()), ('p2', ())))
    # p(1) should be gone
    test.eq(['a', 'p(1)', 'p(2)'], [str(s.symbol) for s in c.symbolic_atoms])


@test
def dependencies(stderr, stdout):
    parse_and_run_tests("""
        base_fact.

        #program one().
        one_fact.

        #program test_base(base).
        cannot(base_fact) :- not base_fact.

        #program test_one(base, one).
        cannot(base_fact) :- not base_fact.
        cannot(one_fact) :- not one_fact.
    """)
    test.eq('', stderr.getvalue())
    test.endswith(stdout.getvalue(),
      "/inputfile.lp\n  base()\n  test_base(base)\n  test_one(base, one)\n")


@test
def run_tests_flag(stdout):
    code = "#program test_a. cannot(true)."
    with test.raises(AssertionError, "cannot(true)"):
        parse_and_run_tests(code, run_tests=True)
    with test.stdout as out:
        parse_and_run_tests(code, run_tests=False)
    test.eq('', out.getvalue())

