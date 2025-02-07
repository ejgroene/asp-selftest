
""" WIP: Clingo drop-in replacement with support for tests and hooks """

import os
import sys
import clingo
import functools

from .session import AspSession
from .error_handling import warn2raise, AspSyntaxError


import selftest
test = selftest.get_tester(__name__)


def save_exception(function):
    @functools.wraps(function)
    def wrap(self, *a, **k):
        try:
            result = function(self, *a, **k)
        except RuntimeError as e:
            assert self.exception, f"{e}: a message should have been logged via logger()"
        if self.exception:
            raise self.exception
        return result
    return wrap


class SyntaxErrorHandler:

    def __init__(this):
        this.exception = None
        this._suppress = None

    @save_exception
    def parse(this, self, parameters):
        self.parse(parameters)

    @save_exception
    def load(this, self, ctl, parameters):
        self.load(ctl, parameters)

    @save_exception
    def ground(this, self, ctl, parameters):
        self.ground(ctl, parameters)

    def logger(this, self, code, message):
        if code == clingo.MessageCode.FileIncluded:
            # always ignore duplicate includes, only warn. @TODO TESTME
            print("Ignoring duplicate #include:", message, file=sys.stderr)
            return
        if this._suppress == code:
            this._suppress = None
            return
        if this.exception:
            print("  WARNING ALREADY exception:", this.exception, file=sys.stdout)
            print("               while logging:", message, file=sys.stdout)
        else:
            if source := self.parameters['source']:
                source = source.splitlines()
            label = self.parameters['label']
            this.exception = warn2raise(source, label, code, message)

    def suppress_logger(this, self, code):
        this._suppress = code

    def check(this, self):
        self.check()
        if this.exception:
            try:
                raise this.exception
            finally:
                this.exception = None

def ground_exc(source, label='test', parts=None, observer=None, context=None):
    class Handler:
        def control(this, self, parameters):
            control = self.control(parameters)
            if observer:
                control.register_observer(observer)
            return control
    with AspSession(source, label=label, context=context, handlers=(SyntaxErrorHandler(), Handler())) as s:
        return s.go_ground(parts=parts)


@test
def ground_exc_with_label():
    with test.raises(AspSyntaxError, "syntax error, unexpected <IDENTIFIER>") as e:
        ground_exc("a.\nan error", label='my code')
    test.eq("""    1 a.
    2 an error
         ^^^^^ syntax error, unexpected <IDENTIFIER>""", e.exception.text)
    test.eq('my code', e.exception.filename)
        


@test
def exception_in_included_file(tmp_path):
    f = tmp_path/'error.lp'
    f.write_text("error")
    old = os.environ.get('CLINGOPATH')
    try:
        os.environ['CLINGOPATH'] = tmp_path.as_posix()
        with test.raises(AspSyntaxError, 'syntax error, unexpected EOF') as e:
            ground_exc("""#include "error.lp".""", label='main.lp')
        test.eq(f.as_posix(), e.exception.filename)
        test.eq(2, e.exception.lineno)
        test.eq('    1 error\n      ^ syntax error, unexpected EOF', e.exception.text)
    finally:
        if old:  #pragma no cover
            os.environ['CLINGOPATH'] = old


@test
def ground_and_solve_basics():
    control = ground_exc("fact.")
    test.eq([clingo.Function('fact')], [s.symbol for s in control.symbolic_atoms.by_signature('fact', 0)])

    control = ground_exc("#program one. fect.", parts=(('one', ()),))
    test.eq([clingo.Function('fect')], [s.symbol for s in control.symbolic_atoms.by_signature('fect', 0)])

    class O:
        @classmethod
        def init_program(self, *a):
            self.a = a
    ground_exc("fict.", observer=O)
    test.eq((True,), O.a)

    class C:
        @classmethod
        def __init__(clz, control):
            pass
        @classmethod
        def goal(self, *a):
            self.a = a
            return a
    ground_exc('foct(@goal("g")).', context=C)
    test.eq("(String('g'),)", str(C.a))


@test
def parse_warning_raise_error():
    with test.raises(AspSyntaxError, "syntax error, unexpected EOF") as e:
        ground_exc("abc", label='code_a')
    test.endswith(e.exception.filename, 'code_a')
    test.eq(2, e.exception.lineno)
    test.eq("    1 abc\n      ^ syntax error, unexpected EOF", e.exception.text)

    with test.raises(AspSyntaxError, 'atom does not occur in any rule head:  b') as e:
        ground_exc("a :- b.")
    test.endswith(e.exception.filename, 'test')
    test.eq(1, e.exception.lineno)
    test.eq("    1 a :- b.\n           ^ atom does not occur in any rule head:  b", e.exception.text)

    with test.raises(AspSyntaxError, 'operation undefined:  ("a"/2)') as e:
        ground_exc('a("a"/2).')
    test.endswith(e.exception.filename, 'test')
    test.eq(1, e.exception.lineno)
    test.eq('    1 a("a"/2).\n        ^^^^^ operation undefined:  ("a"/2)',
            e.exception.text)

    with test.raises(AspSyntaxError, "unsafe variables in:  a(A):-[#inc_base];b.") as e:
        ground_exc('a(A)  :-  b.', label='code b')
    test.endswith(e.exception.filename, 'code b')
    test.eq(1, e.exception.lineno)
    test.eq("""    1 a(A)  :-  b.
        ^ 'A' is unsafe
      ^^^^^^^^^^^^ unsafe variables in:  a(A):-[#inc_base];b.""",
            e.exception.text)

    with test.stdout as out:
        with test.raises(AspSyntaxError, "global variable in tuple of aggregate element:  X") as e:
            ground_exc('a(1). sum(X) :- X = #sum { X : a(A) }.')
        test.endswith(e.exception.filename, 'test')
        test.eq(1, e.exception.lineno)
        test.eq("""    1 a(1). sum(X) :- X = #sum { X : a(A) }.
                                 ^ global variable in tuple of aggregate element:  X""",
                e.exception.text)
        test.startswith(
                out.getvalue(),
                "  WARNING ALREADY exception: global variable in tuple of aggregate element:  X (test, line 1)")


@test
def unsafe_variables():
    with test.raises(AspSyntaxError, "unsafe variables in:  output(A,B):-[#inc_base];input.") as e:
        ground_exc("""
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
def multiline_error():
    with test.raises(AspSyntaxError,
                     "unsafe variables in:  geel(R):-[#inc_base];iets_vrij(S);(S,T,N)=R;R=(S,T,N)."
                     ) as e:
        ground_exc("""
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
def duplicate_const():
    with test.raises(AspSyntaxError, "redefinition of constant:  #const a=43.") as e:
        ground_exc("""
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
    with test.raises(AspSyntaxError) as e:
        with AspSession(files=[code.as_posix()], handlers=(SyntaxErrorHandler(),)) as s:
            pass
        test.endswith(e.exception.text, """
    1 oops(().
             ^ syntax error, unexpected ., expecting ) or ;""")
