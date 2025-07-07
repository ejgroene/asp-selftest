import shutil
import enum
import itertools
import tempfile
from unittest import mock
import clingo

import selftest
test = selftest.get_tester(__name__)


NA = clingo.String("N/A")

            
# ExitCode, see clasp_app.h
class ExitCode(enum.IntEnum):
    UNKNOWN   =   0  #/*!< Satisfiability of problem not known; search not started.   */
    INTERRUPT =   1  #/*!< Run was interrupted.                                       */
    SAT       =  10  #/*!< At least one model was found.                              */
    EXHAUST   =  20  #/*!< Search-space was completely examined.                      */
    MEMORY    =  33  #/*!< Run was interrupted by out of memory exception.            */
    ERROR     =  65  #/*!< Run was interrupted by internal error.                     */
    NO_RUN    = 128  #/*!< Search not started because of syntax or command line error.*/
 

def write_file(file, text):
    file.write_text(text)
    return file.as_posix()


def write_tempfile(suffix, data):
    f = tempfile.NamedTemporaryFile('w', suffix=suffix)
    f.write(data)
    f.flush()
    return f


def list_symbols(control):
    return [str(a.symbol) for a in control.symbolic_atoms]


def create_control(arguments=(), logger=None, **etc):
    new_args=list(itertools.dropwhile(lambda p: not p.startswith('--'), arguments))
    return clingo.Control(arguments=new_args, logger=logger)


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


def is_plugin_instruction(p, givenname='insert_plugin'):
    """ check if p is a processor(<classname>) and return <classname> """
    if p.ast_type == clingo.ast.ASTType.Rule:
        p = p.head
        if p.ast_type == clingo.ast.ASTType.Literal:
            p = p.atom
            if p.ast_type == clingo.ast.ASTType.SymbolicAtom:
                p = p.symbol
                if p.ast_type == clingo.ast.ASTType.Function:
                    name, args = p.name, p.arguments
                    if name == givenname:
                        p = args[0]
                        if p.ast_type == clingo.ast.ASTType.SymbolicTerm:
                            p = p.symbol
                            if p.type == clingo.symbol.SymbolType.String:
                                p = p.string
                                if isinstance(p, str):
                                    return p


