import traceback
import re

import selftest
test = selftest.get_tester(__name__)


CR = '\n' # trick to support old python versions that do not accecpt \ in f-strings


class AspSyntaxError(Exception):
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



def warn2raise(lines, label, errors, code, msg):
    """ Clingo calls this, but can't handle exceptions well, so we wrap everything. """
    try:
        messages = parse_message(msg)
        file, line, start, end, key, msg, more = messages[0]
        if file == '<block>':
            name = repr(label) if label else "ASP code"
            srclines = lines
        else:
            name = file
            srclines = [l.removesuffix('\n') for l in open(file).readlines()]
        srclines = [f"{n:3} {line}" for n, line in enumerate(srclines, 1)]
        msg_fmt = lambda: f"    {' ' * (start-1)}{'^' * (end-start)} {m}{r}"
        offset = 0
        for _, line, start, end, _, m, r in sorted(messages[1:]):
            srclines.insert(line + offset, msg_fmt())
            offset += 1 
        _, line, start, end, _, m, r = messages[0]
        srclines.insert(line + len(messages) -1, msg_fmt())
        snippet = srclines[max(0,line-10):line+10]  # TODO testme
        if "file could not be opened" in m:
            snippet.append(f"CLINGOPATH={os.environ.get('CLINGOPATH')}")
        errors.append(AspSyntaxError(f"in {name}, line {line}:{CR}{CR.join(snippet)}"))
    except BaseException as e:
        """ unexpected exception in the code above """
        traceback.print_exc()
        exit(-1)
