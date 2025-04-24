
import sys
import io
import collections
import shutil
import itertools
import clingo
import threading
import inspect
import unittest.mock as mock
from unittest.mock import Mock

import selftest
test = selftest.get_tester(__name__)


SymbolTypeFunction = clingo.SymbolType.Function

from .session import CompoundContext


def has_name(symbol, name):
   return symbol.type == SymbolTypeFunction and symbol.name == name


def print_test_result(result):
    name = result['testname']
    models = result['models']
    print(f"ASPUNIT: {name}: ", end='', flush=True)
    print(f" {models} model{'s' if models>1 else ''}")


CR = '\n' # trick to support old python versions that do not accecpt \ in f-strings
def batched(iterable, n):
    """ not in python < 3.12 """
    # batched('ABCDEFG', 3) → ABC DEF G
    if n < 1:
        raise ValueError('n must be at least one')
    iterator = iter(iterable)
    while batch := tuple(itertools.islice(iterator, n)):
        yield batch

@test
def batch_it():
    test.eq([], list(batched([], 1)))
    test.eq([(1,)], list(batched([1], 1)))
    test.eq([(1,),(2,)], list(batched([1,2], 1)))
    test.eq([(1,)], list(batched([1], 2)))
    test.eq([(1,2)], list(batched([1,2], 2)))
    test.eq([(1,2), (3,)], list(batched([1,2,3], 2)))
    with test.raises(ValueError, 'n must be at least one'):
        list(batched([], 0))


def format_symbols(symbols):
    symbols = sorted(str(s).strip()for s in symbols)
    if len(symbols) > 0:
        col_width = (max(len(w) for w in symbols)) + 2
        width, h = shutil.get_terminal_size((120, 20))
        cols = width // col_width
        modelstr = '\n'.join(
                ''.join(s.ljust(col_width) for s in b).strip()
            for b in batched(symbols, max(cols, 1)))
    else:
        modelstr = "<empty>"
    return modelstr


@test
def format_symbols_basic():
    test.eq('a', format_symbols(['a']))
    test.eq('a  b  c  d', format_symbols(['a', 'b', 'c', 'd']))
    test.eq('a  b  c  d', format_symbols([' a  ', '\tb', '\nc\n', '  d '])) # strip
    with mock.patch("shutil.get_terminal_size", lambda _: (10,20)):
        test.eq('a  b  c\nd', format_symbols(['a', 'b', 'c', 'd']))
    with mock.patch("shutil.get_terminal_size", lambda _: (8,20)):
        test.eq('a  b\nc  d', format_symbols(['a', 'b', 'c', 'd']))
    with mock.patch("shutil.get_terminal_size", lambda _: (4,20)):
        test.eq('a\nb\nc\nd', format_symbols(['a', 'b', 'c', 'd']))


def create_assert(*args):
    if len(args) > 1:
        args = clingo.Function('', args)
    else:
        args = args[0]
    return args, clingo.Function("assert", (args,))


@test
def create_some_asserts():
    Number = clingo.Number
    Function = clingo.Function
    test.eq((Number(3), Function('assert', [Number(3)])),
            create_assert(Number(3)))
    test.eq((Function('', [Number(4), Number(2)]), Function('assert', [Function('', [Number(4), Number(2)])])),
            create_assert(Number(4), Number(2)))


class Tester:

    def __init__(self, filename, name):
        self._filename = filename
        self._name = name
        self._models_ist = 0
        self._models_soll = -1
        self._current_rule = None
        self.failures = []
        self.constraints = []
        self._symbols = {}
        self._rules = collections.defaultdict(set)


    def on_model(self, model):
        """ Callback when model is found; count model and check all asserts. """
        by_signature = model.context.symbolic_atoms.by_signature
        if self._models_soll == -1:
            models = next(by_signature('models', 1), None)
            if models:
                self._models_soll = models.symbol.arguments[0].number
        self._models_ist += 1

        def find_constraints(*names):
            for name in names:
                for arity in (1,2):
                    for symbolic_atom in by_signature(name, arity):
                        # TODO TEST (although I still don't know how to trigger)
                        #if symbolic_atom.is_fact: <= this is NOT the same condition as model.is_true
                        if model.is_true(symbolic_atom.literal):
                            yield symbolic_atom

        alternative_predicates = ['constraint', 'cannot']
        for constraint in find_constraints(*alternative_predicates):
            self.constraints.append(constraint.symbol)

        failures = self.constraints
        if failures:
            modelstr = format_symbols(s for s in model.symbols(shown=True) if s.name not in alternative_predicates)
            self.failures.append(AssertionError(
                f"MODEL:\n{modelstr}\n"
                f"Failures in {self._filename}, #program {self._name}():\n"
                f"{', '.join(map(str, failures))}\n"))
            return False
        return True


    def report(self):
        """ When done, check assert(@models(n)) explicitly, then report. """
        if self.failures:
            assert len(self.failures) == 1, self.failures
            raise self.failures[0]
        models = self._models_ist
        if self._models_soll > -1:
            if self._models_soll != self._models_ist:
                raise Exception(f"Expected {self._models_soll} models, found {models}.")
        elif models == 0:
            # if no model count specified, then raise when no models are found
            raise Exception(f"{self._filename} #program {self._name}: no models found.")
        return dict(models=models)



class TesterHook:

    def __init__(this, on_report=print_test_result):
        this.on_report = on_report

    def parse(this, self, **kwargs):
        ast, files = this._parse(self, **kwargs)
        this.files = files
        return ast

    def _parse(this, self, source=None, files=None, callback=None,
               control=None, logger=None, message_limit=1, piggies=None):

        logger = logger if logger else self.logger

        def suppress_include(code, message):
            if code != clingo.MessageCode.FileIncluded and logger:
                logger(code, message)

        ast, files = gather_tests(
                parse=self.next.parse,
                source=source,
                files=files,
                callback=callback,
                control=control,
                logger=suppress_include,
                message_limit=message_limit)

        piggies.update(ast=ast, files=files)

        return ast, files


    def ground(this, self, control, parameters, piggies=None):
        """ Grounds and solves the tests in each included file separately. """
        for filename, programs in this.files.items():

            tests = {p:deps for p,deps in programs.items() if p.startswith('test_')}
            if tests:
                print(F"ASP FILE: {filename}, tests: {len(tests)}.", file=sys.stderr)

                if filename == '<string>':
                    fileast, files = piggies['ast'], piggies['files']
                else:
                    fileast, files = this._parse(
                            self,
                            files=[filename],
                            piggies=piggies)

                for includedfilename in files:
                    if includedfilename != filename:
                        print("  includes:", includedfilename, file=sys.stderr)

            for prog_name, dependencies in tests.items():
                parts = [(prog_name, [clingo.Number(42) for _ in dependencies])] + \
                        [(dep_name, []) for dep_name in dependencies]

                tester = Tester(filename, prog_name)
                # We want to use a fresh control, and honor the existing handlers,
                # so we derive our parameters from the existing ones, create a new
                # control and dutyfully call self.[load|ground|solve]().
                with parameters['context'].avec(tester) as testcontext:
                    testparms = dict(parameters,
                                     ###ast=parameters['ast'][:],    # don't let it grow with each test
                                     ast=fileast,
                                     parts=parts,
                                     context=testcontext,  #parameters['context'].avec(tester),
                                     solve_options={'on_model': tester.on_model})
                    # this is a very limited way of supplying the original command line arguments to the control
                    args = [a for a in testparms['arguments'] if a not in testparms['files']]
                    testcontrol = clingo.Control(args, logger=self.logger, message_limit=1)
                    #testcontrol.register_observer(tester)
                    self.load(testcontrol, testparms)
                    self.next.ground(testcontrol, testparms)
                    self.solve(testcontrol, testparms)
                    report = tester.report() | {'filename': filename, 'testname': prog_name}
                    this.on_report(report)
        self.next.ground(control, parameters)

from clingo.ast import ASTType

def is_program(a):
    if a.ast_type == ASTType.Program:
        return a.name, [p.name for p in a.parameters]

def is_generated_base(a):
    return a.ast_type == ASTType.Program and a.name == 'base' and a.location.begin.column == a.location.end.column == 1

import clingo
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
def report_not_for_base_model_count():
    t = Tester('filea.lp', 'harry')
    with test.raises(Exception, 'filea.lp #program harry: no models found.'):
        t.report()
    t = Tester('fileb.lp', 'base')
    t.on_model(Mock(context=Mock(symbolic_atoms=Mock(by_signature=Mock(return_value=iter([Mock(symbol=Mock(arguments=[Mock(number=1)]))]))))))
    r = t.report()
    test.eq({'models': 1}, r)


def gather_tests(parse, source=None, files=None, callback=None,
                 control=None, logger=None, message_limit=20):
    programs = {}
    global_ast = []

    def process_node(node):
        if callback:
            callback(node)
        global_ast.append(node)
        filename = node.location.begin.filename
        if filename not in programs:
            programs[filename] = {}
        if program := is_program(node):
            name, dependencies = program
            current_program = name
            if name.startswith('test_'):
                if name in programs[filename]:
                    raise Exception(f"Duplicate test: {name!r} found in {filename}.")
                programs[filename][name] = dependencies

    parse(source=source,
          files=files,
          callback=process_node,
          control=control,
          logger=logger,
          message_limit=message_limit)

    return global_ast, programs


@test
def run_unit_test_separately_on_include(tmp_path):
    part_a = tmp_path/'part_a.lp'
    part_b = tmp_path/'part_b.lp'
    part_c = tmp_path/'part_c.lp'
    part_a.write_text(f'part(a).  #program test_a.  a.  cannot(fail_a).')
    part_b.write_text(f'part(b).  #include "{part_a}".  b.  #program test_b.  cannot(fail_b).')
    part_c.write_text(f'part(c).  #include "{part_b}".  c.  #include "{part_a}".  #program test_c.  cannot(fail_c).')
    def parse(source=None, **kw):
        clingo.ast.parse_files(**kw)
    ast, programs = gather_tests(parse, files=[str(part_c)])
    programs_a = programs[str(part_a)]
    programs_b = programs[str(part_b)]
    programs_c = programs[str(part_c)]
    test.eq(3, len(programs))

    test.eq({'test_a': []}, programs_a)
    test.eq({'test_b': []}, programs_b)
    test.eq({'test_c': []}, programs_c)

    test.eq([
        '#program base.',
        'part(c).',
        'part(b).',
        'part(a).',
        '#program test_a.',
        'a.',
        'cannot(fail_a).',
        '#program base.',
        'b.',
        '#program test_b.',
        'cannot(fail_b).',
        '#program base.',
        'c.',
        '#program test_c.',
        'cannot(fail_c).'
        ], [str(a) for a in ast])


def do_parse(source):
    ast = []
    def parse(source=None, **kw):
        clingo.ast.parse_files(**kw)
    def callback(node):
        ast.append(node)
    data = gather_tests(parse, files=[str(source)], callback=callback)
    return ast, data


@test
def file_with_only_include(tmp_path):
    part_a = tmp_path/'part_a.lp'
    part_b = tmp_path/'part_b.lp'
    part_c = tmp_path/'part_c.lp'
    part_a.write_text(f'part(a).')
    part_b.write_text(f'#include "{part_a}".')
    part_c.write_text(f'#include "{part_b}".')
    ast, _ = do_parse(part_c)
    test.eq(['#program base.', 'part(a).', '#program base.', '#program base.'], [str(a) for a in ast])

@test
def file_with_include_in_program(tmp_path):
    part_a = tmp_path/'part_a.lp'
    part_b = tmp_path/'part_b.lp'
    part_c = tmp_path/'part_c.lp'
    part_a.write_text(f'part(a).')
    part_b.write_text(f'#include "{part_a}".')
    part_c.write_text(f'#program aap.  #include "{part_b}".')
    ast, _ = do_parse(part_c)
    test.eq(['#program base.', '#program aap.', 'part(a).', '#program base.', '#program base.'], [str(a) for a in ast])
