import shutil
import itertools
from unittest import mock
import clingo

import selftest
test = selftest.get_tester(__name__)


NA = clingo.String("N/A")


def Noop(next, *args, **kwargs):
    return next(*args, **kwargs)


def write_file(file, text):
    file.write_text(text)
    return file.as_posix()


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

