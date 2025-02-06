import traceback
import re
import os
import math
import pathlib

import clingo

import selftest
test = selftest.get_tester(__name__)


CR = '\n' # trick to support old python versions that do not accecpt \ in f-strings


class AspSyntaxError(SyntaxError):
    pass


def parse_message(msg):
    return [(file,
             int(end_line_or_col if opt_end_col else start_line),
             int(start_col),
             int(opt_end_col if opt_end_col else end_line_or_col),
             key, msg, more) 
            for file, start_line, start_col, end_line_or_col, opt_end_col, key, msg, more
            in re.findall(r"(?m)^(.+?):(\d+):(\d+)-(\d+)(?::(\d+))?:\s(.+?):\s([^\n]+)(?:\n(\s\s.+))?", msg)]


@test
def parse_clingo_error_messages():
    test.eq([('<block>', 1, 6, 7, 'info', 'atom does not occur in any rule head:', '  b')],
            parse_message("<block>:1:6-7: info: atom does not occur in any rule head:\n  b"))
    test.eq([('<block>', 1, 4, 9, 'error', 'syntax error, unexpected <IDENTIFIER>', '')],
            parse_message("<block>:1:4-9: error: syntax error, unexpected <IDENTIFIER>"))
    test.eq([('/var/folders/fn/2hl6h1jn4772vw7j9hlg9zjm0000gn/T/tmpfy706dra/error.lp', 2, 1, 2,
              'error', 'syntax error, unexpected EOF', '')],
            parse_message("/var/folders/fn/2hl6h1jn4772vw7j9hlg9zjm0000gn/T/tmpfy706dra/error.lp:2:1-2:"
                          " error: syntax error, unexpected EOF"))
    test.eq([('<block>', 1, 3, 8, 'info', 'operation undefined:', '  ("a"/2)')],
            parse_message('<block>:1:3-8: info: operation undefined:\n  ("a"/2)'))
    test.eq([('<blOck>', 1, 1, 11, 'error', 'unsafe variables in:', '  a(A):-[#inc_base];b.'),
             ('<block>', 1, 3, 4, 'note', "'A' is unsafe", '')],
            parse_message("""<blOck>:1:1-11: error: unsafe variables in:
  a(A):-[#inc_base];b.
<block>:1:3-4: note: 'A' is unsafe"""))
    test.eq([('<block>', 1, 7, 39, 'error', 'unsafe variables in:', '  sum(X):-[#inc_base];X=#sum{X:a(A)}.'),
             ('<block>', 1, 11, 12, 'note', "'X' is unsafe", '')],
            parse_message("""<block>:1:7-39: error: unsafe variables in:
  sum(X):-[#inc_base];X=#sum{X:a(A)}.
<block>:1:11-12: note: 'X' is unsafe"""))
    test.eq([('<block>', 3, 13, 37, 'error', 'unsafe variables in:', '  output(A,B):-[#inc_base];input.'),
             ('<block>', 3, 20, 21, 'note', "'A' is unsafe", ''),
             ('<block>', 3, 23, 24, 'note', "'B' is unsafe", '')],
            parse_message("""<block>:3:13-37: error: unsafe variables in:
  output(A,B):-[#inc_base];input.
<block>:3:20-21: note: 'A' is unsafe
<block>:3:23-24: note: 'B' is unsafe"""))
    test.eq([('<block>', 3, 13, 43, 'error', 'unsafe variables in:', '  geel(R):-[#inc_base];iets_vrij(S);(S,T,N)=R;R=(S,T,N).'),
             ('<block>', 3, 40, 41, 'note', "'N' is unsafe", ''),
             ('<block>', 2, 18, 19, 'note', "'R' is unsafe", ''),
             ('<block>', 3, 37, 38, 'note', "'T' is unsafe", '')
             ],
            parse_message("""<block>:2:13-3:43: error: unsafe variables in:
  geel(R):-[#inc_base];iets_vrij(S);(S,T,N)=R;R=(S,T,N).
<block>:3:40-41: note: 'N' is unsafe
<block>:2:18-19: note: 'R' is unsafe
<block>:3:37-38: note: 'T' is unsafe"""), diff=test.diff)



def warn2raise(lines, label, code, msg):
    """ Clingo calls this, but can't handle exceptions well, so we wrap everything. """
    try:
        # deal with '<cmd>' (command line) error messages separately
        if msg and msg.startswith('<cmd>'):
            return RuntimeError(msg)
        messages = parse_message(msg)
        file, line, start, end, key, msg, more = messages[0]
        name = label if label else '<asp code>'
        srclines = lines if lines else []
        if file == '<block>':
            srclines = lines if lines else []
        elif pathlib.Path(file).exists():
            name = file
            srclines = [l.removesuffix('\n') for l in open(file).readlines()]
        w = 1
        max_lineno = len(srclines)
        nr_width = 1 + int(math.log10(max_lineno)) if max_lineno > 0 else 0
        srclines = [f"    {n:{nr_width}} {line}" for n, line in enumerate(srclines, 1)]
        msg_fmt = lambda: f"   {' ':{nr_width}}  {' ' * (start-1)}{'^' * (end-start)} {m}{r}"
        offset = 0
        for _, line, start, end, _, m, r in sorted(messages[1:]):
            srclines.insert(line + offset, msg_fmt())
            offset += 1 
        _, line, start, end, _, m, r = messages[0]
        srclines.insert(line + len(messages) -1, msg_fmt())
        snippet = srclines[max(0,line-10):line+10]  # TODO testme

        if "file could not be opened" in m:
            snippet.append(f"CLINGOPATH={os.environ.get('CLINGOPATH')}")
        se = AspSyntaxError(msg + r, (name, line, None, CR.join(snippet)))
        return se
    except BaseException as e:
        """ unexpected exception in the code above """
        traceback.print_exc()
        exit(-1)


# NB: most tests dor warn2raise are still in runasptests.py, indirectly checking for SyntaxError's
@test
def raise_warnings_as_exceptions(stderr):
    try:
        warn2raise(None, None, None, None)
    except SystemExit as e:
        test.eq(-1, e.code)
    msg = stderr.getvalue()
    test.startswith(msg, "Traceback (most recent call last):")
    test.endswith(msg, "TypeError: expected string or bytes-like object, got 'NoneType'\n")


@test
def deal_with_command_line_errors():
    e = warn2raise(None, None, None, "<cmd>: all wrong!")
    test.eq(RuntimeError, type(e))
    test.eq(('<cmd>: all wrong!',), e.args)


@test
def print_clingo_path_on_file_could_not_be_opened():
    old = os.environ.get('CLINGOPATH', None)
    os.environ['CLINGOPATH'] = 'paf'
    try:
        error = warn2raise([], 'no-file', None, "<block>:3:4-5: info: file could not be opened:\n  dus")
        test.isinstance(error, AspSyntaxError)
        test.eq("no-file", error.filename)
        test.eq(3, error.lineno)
        test.eq(None, error.offset)
        test.eq('         ^ file could not be opened:  dus\nCLINGOPATH=paf', error.text)
        test.eq('file could not be opened:  dus', error.msg)
    finally:
        if old:
            os.environ['CLINGOPATH'] = old


@test
def make_snippet_witg_proper_indent():
    src_lines = ['%1', '%2','%3','%4','%5','%6','%7','%8','%9','%10','error']
    error = warn2raise(src_lines, None, 'code', "<block>:11:1-6: info: hier moet een punt staan:\n  snappie?")
    test.eq("""     2 %2
     3 %3
     4 %4
     5 %5
     6 %6
     7 %7
     8 %8
     9 %9
    10 %10
    11 error
       ^^^^^ hier moet een punt staan:  snappie?""",
        error.text, diff=test.diff)

@test
def nieuw_geval():
    source = """a.
an error"""
    error = warn2raise(source.splitlines(), None, 'code', '<string>:2:4-9: error: syntax error, unexpected <IDENTIFIER>')
    test.eq("""    1 a.
    2 an error
         ^^^^^ syntax error, unexpected <IDENTIFIER>""", error.text)

