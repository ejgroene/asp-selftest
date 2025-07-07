import os
import itertools
import clingo

from .messageparser import warn2raise
from .misc import write_file

import selftest
test = selftest.get_tester(__name__)


def msg2exc(code, message):
    return warn2raise(None, None, code, message)


def clingo_syntaxerror_plugin(next, msg2exc=msg2exc, **etc):
    """ Takes clingo log message to raise rich exception."""

    _logger, _main = next(**etc)

    exceptions = []

    def logger(code, message):
        #_logger(code, message)
        rich_exception = msg2exc(code, message)
        exceptions.append(rich_exception)

    def main():
        try:
            result = _main() # expect Clingo to call logger on error
        except RuntimeError as e:
            if not exceptions:
                raise e
        if exceptions:
            notes = ((s, len(tuple(n))) for s, n in itertools.groupby(exceptions[1:], lambda e: f"followed by: {e}"))
            x = [f"{s} (repeated {n} times)" if n > 1 else s for s, n in notes]
            exceptions[0].__notes__ = x
            raise exceptions[0]
        return result
            
    return logger, main


@test
def syntaxerror_basics():
    
    def next(control=None):
        def next_main():
            control(42, "not good") # fake; but we only want to trigger logger
            raise RuntimeError
        def next_logger(code, message):
            pass
        return next_logger, next_main
        
    # we fake the control and directly pass the logger
    def prime_logger(code, message):
        logger(code, message)
            
    logger, main = clingo_syntaxerror_plugin(next, control=prime_logger, msg2exc=lambda code, msg: SyntaxError(msg))
        
    with test.raises(SyntaxError, "not good"):
        main()

    # TODO somehow test mapping the code/message to a fully specified
    #      SyntaxError separately (mapping code in messageparser.py)
    #      - test passing etc
    #      - test calling next_logger
    # warn2raise(lines, label, code, msg)


def run_syntaxerror_plugin(tmp_path, source=None, label='test', files=(), parts=(('base', ()),)):
    if source:
        f = write_file(tmp_path/label, source)
        files = (f, *files)
    def next(**_):
        def load_and_ground():
            for f in files:
                control.load(f)
            control.ground()
            return "done"
        return lambda x,y: None, load_and_ground
    logger, main = clingo_syntaxerror_plugin(next)
    control = clingo.Control(logger=logger)
    return main()


@test
def return_result_when_no_error(tmp_path):
    result = run_syntaxerror_plugin(tmp_path, "a.")
    test.eq('done', result)


@test
def exc_with_label(tmp_path):
    with test.raises(SyntaxError, "syntax error, unexpected <IDENTIFIER>") as e:
        run_syntaxerror_plugin(tmp_path, "a.\nan error", label='my code')
    test.eq("""    1 a.
    2 an error
         ^^^^^ syntax error, unexpected <IDENTIFIER>""", e.exception.text)
    test.endswith(e.exception.filename, 'my code')


@test
def exception_in_included_file(tmp_path):
    f = tmp_path/'error.lp'
    f.write_text("error")
    old = os.environ.get('CLINGOPATH')
    try:
        os.environ['CLINGOPATH'] = tmp_path.as_posix()
        with test.raises(SyntaxError, 'syntax error, unexpected EOF') as e:
            run_syntaxerror_plugin(tmp_path, """#include "error.lp".""", label='main.lp')
        test.eq(f.as_posix(), e.exception.filename)
        test.eq(2, e.exception.lineno)
        test.eq('    1 error\n      ^ syntax error, unexpected EOF', e.exception.text)
    finally:
        if old:  #pragma no cover
            os.environ['CLINGOPATH'] = old


@test
def parse_warning_raise_error(tmp_path):
    with test.raises(SyntaxError, "syntax error, unexpected EOF") as e:
        run_syntaxerror_plugin(tmp_path, "abc", label='code_a')
    test.endswith(e.exception.filename, 'code_a')
    test.eq(2, e.exception.lineno)
    test.eq("    1 abc\n      ^ syntax error, unexpected EOF", e.exception.text)

    with test.raises(SyntaxError, 'atom does not occur in any rule head:  b') as e:
        run_syntaxerror_plugin(tmp_path, "a :- b.")
    test.endswith(e.exception.filename, 'test')
    test.eq(1, e.exception.lineno)
    test.eq("    1 a :- b.\n           ^ atom does not occur in any rule head:  b", e.exception.text)

    with test.raises(SyntaxError, 'operation undefined:  ("a"/2)') as e:
        run_syntaxerror_plugin(tmp_path, 'a("a"/2).')
    test.endswith(e.exception.filename, 'test')
    test.eq(1, e.exception.lineno)
    test.eq('    1 a("a"/2).\n        ^^^^^ operation undefined:  ("a"/2)',
            e.exception.text)

    with test.raises(SyntaxError, "unsafe variables in:  a(A):-[#inc_base];b.") as e:
        run_syntaxerror_plugin(tmp_path, 'a(A)  :-  b.', label='code b')
    test.endswith(e.exception.filename, 'code b')
    test.eq(1, e.exception.lineno)
    test.eq("""    1 a(A)  :-  b.
        ^ 'A' is unsafe
      ^^^^^^^^^^^^ unsafe variables in:  a(A):-[#inc_base];b.""",
            e.exception.text)

    with test.stdout as out:
        with test.raises(SyntaxError, "global variable in tuple of aggregate element:  X") as e:
            run_syntaxerror_plugin(tmp_path, 'a(1). sum(X) :- X = #sum { X : a(A) }.')
        test.endswith(e.exception.filename, 'test')
        test.eq(1, e.exception.lineno)
        test.eq("""    1 a(1). sum(X) :- X = #sum { X : a(A) }.
                                 ^ global variable in tuple of aggregate element:  X""",
                e.exception.text)
        test.eq(['followed by: unsafe variables in:  sum(X):-[#inc_base];X=#sum{X:a(A)}. (test, line 1)'],
            e.exception.__notes__)
        #test.startswith(
        #        out.getvalue(),
        #        "  WARNING ALREADY exception: global variable in tuple of aggregate element:  X (test, line 1)")


@test
def unsafe_variables(tmp_path):
    with test.raises(SyntaxError, "unsafe variables in:  output(A,B):-[#inc_base];input.") as e:
        run_syntaxerror_plugin(tmp_path, """
            input.
            output(A, B)  :-  input.
            % comment""")
    test.endswith(e.exception.filename, 'test')
    test.eq(3, e.exception.lineno)
    test.eq("""    1 
    2             input.
    3             output(A, B)  :-  input.
                         ^ 'A' is unsafe
                            ^ 'B' is unsafe
                  ^^^^^^^^^^^^^^^^^^^^^^^^ unsafe variables in:  output(A,B):-[#inc_base];input.
    4             % comment""", e.exception.text)


@test
def multiline_error(tmp_path):
    with test.raises(SyntaxError,
                     "unsafe variables in:  geel(R):-[#inc_base];iets_vrij(S);(S,T,N)=R;R=(S,T,N)."
                     ) as e:
        run_syntaxerror_plugin(tmp_path, """
            geel(R)  :-
                iets_vrij(S), R=(S, T, N).
            %%%%""")
    test.endswith(e.exception.filename, 'test')
    test.eq(3, e.exception.lineno)
    test.eq("""    1 
    2             geel(R)  :-
                       ^ 'R' is unsafe
    3                 iets_vrij(S), R=(S, T, N).
                                          ^ 'T' is unsafe
                                             ^ 'N' is unsafe
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ unsafe variables in:  geel(R):-[#inc_base];iets_vrij(S);(S,T,N)=R;R=(S,T,N).
    4             %%%%""", e.exception.text)


@test
def duplicate_const(tmp_path):
    with test.raises(SyntaxError, "redefinition of constant:  #const a=43.") as e:
        run_syntaxerror_plugin(tmp_path, """
            #const a = 42.
            #const a = 43.
            """, parts=[('base', ()), ('p1', ()), ('p2', ())])
    test.endswith(e.exception.filename, 'test')
    test.eq(3, e.exception.lineno)
    test.eq("""    1 
    2             #const a = 42.
                  ^^^^^^^^^^^^^^ constant also defined here
    3             #const a = 43.
                  ^^^^^^^^^^^^^^ redefinition of constant:  #const a=43.
    4             """, e.exception.text, diff=test.diff)


@test
def error_in_file(tmp_path):
    code = tmp_path/'code.lp'
    code.write_text('oops(().')
    with test.raises(SyntaxError) as e:
        with run_syntaxerror_plugin(tmp_path, files=[code.as_posix()]) as s:
            s.go_prepare()
        test.endswith(e.exception.text, """
    1 oops(().
             ^ syntax error, unexpected ., expecting ) or ;""")


@test
def do_not_mask_other_exceptions(stdout):

    def next_plugin():
        def main():
            raise Exception("do not mask me")
        return None, main
       
    _, main = clingo_syntaxerror_plugin(next_plugin)
    with test.raises(Exception, "do not mask me"):
        main()


@test
def detect_runtimerror_without_logged_error(stdout):

    def next_plugin():
        def main():
            raise RuntimeError("no logger called")
        return None, main

    _, main = clingo_syntaxerror_plugin(next_plugin)
    with test.raises(RuntimeError, "no logger called"):
        main()


@test
def raise_exception_in_context():

    class Context:
        def f(self):
            1/0

    def next_plugin():
        def main():
            control.add("a(@f()).")
            control.ground(context=Context())
        return lambda c, m: None, main

    logger, main = clingo_syntaxerror_plugin(next_plugin)
    control = clingo.Control(logger=logger)
    with test.raises(ZeroDivisionError, "division by zero"):
        main()


@test
def count_repeated_errors():
    def next_plugin():
        def main():
            control.add("a(@f()). b(@f()). c(@f()).")
            control.ground()
        return lambda c, m: None, main
    logger, main = clingo_syntaxerror_plugin(next_plugin)
    control = clingo.Control(logger=logger)
    with test.raises(SyntaxError, "operation undefined:  function 'f' not found") as e:
        main()
    test.eq(["followed by: operation undefined:  function 'f' not found (<asp code>, line 1) (repeated 2 times)"], e.__notes__)

