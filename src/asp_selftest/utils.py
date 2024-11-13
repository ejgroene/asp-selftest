import sys
import clingo
import functools
import inspect
import traceback


import selftest
test = selftest.get_tester(__name__)


def find_symbol(ctl, name, arity=0):
    return str(next(ctl.symbolic_atoms.by_signature(name, arity)).symbol)


def is_processor_predicate(p):
    """ check if p is a processor(<classname>) and return <classname> """
    if p.ast_type == clingo.ast.ASTType.Rule:
        p = p.head
        if p.ast_type == clingo.ast.ASTType.Literal:
            p = p.atom
            if p.ast_type == clingo.ast.ASTType.SymbolicAtom:
                p = p.symbol
                if p.ast_type == clingo.ast.ASTType.Function:
                    name, args = p.name, p.arguments
                    if name == 'processor':
                        p = args[0]
                        if p.ast_type == clingo.ast.ASTType.SymbolicTerm:
                            p = p.symbol
                            if p.type == clingo.symbol.SymbolType.String:
                                p = p.string
                                if isinstance(p, str):
                                    return p


def locals(name):
    f = inspect.currentframe().f_back
    while f := f.f_back:
        if value := f.f_locals.get(name):
            yield value


@test
def find_locals():
    l = 1
    test.eq([], list(locals('l')))
    def f():
        l = 2
        test.eq([1], list(locals('l')))
        def g():
            l= 3
            test.eq([2, 1], list(locals('l')))
        g()
    f()


def delegate(function):
    """ Decorator for delegating methods to processors """
    @functools.wraps(function)
    def dispatch(self, *args, **kwargs):
        for this in self.delegates:
            if handler := getattr(this, function.__name__, None):
                if handler in locals('handler'):
                    continue
                return handler(self, *args, **kwargs)
        seen = ', '.join(sorted(set(l.__qualname__ for l in locals('handler'))))
        raise AttributeError(f"No more {function.__name__!r} found after: {seen}")
    return dispatch


@test
def delegation_none():
    class B:
        delegates = ()
        @delegate
        def f(self):
            pass
    with test.raises(AttributeError):
        B().f()


@test
def delegation_one():
    class A:
        def f(this, self):
            return this, self
    a = A()
    class B:
        delegates = (a,)
        @delegate
        def f(self):
            pass
    b = B()
    test.eq((a, b), b.f())


@test
def delegation_loop():
    class A:
        def f(this, self):
            return self.f()
    a = A()
    class B:
        delegates = (a,)
        @delegate
        def f(self):
            pass
    with test.raises(AttributeError):
        B().f()


@test
def delegation_loop_back_forth():
    class A:
        def f(this, self):
            return self.f()
    a = A()
    class B:
        def f(this, self):
            return self.f()
    b = B()
    class C:
        delegates = (a, b)
        @delegate
        def f(self):
            pass
    with test.raises(
            AttributeError,
            "No more 'f' found after: delegation_loop_back_forth.<locals>.A.f, delegation_loop_back_forth.<locals>.B.f"):
        C().f()


@test
def delegation():
    class B:
        def f(this, self):
            return self.g() * self.h() * this.i() # 5 * 3 * 2
        def h(this, self):
            return 3
        def i(self):
            return 2
    class C:
        def g(this, self):
            return 5
        def i(this, self):
            return 7
    class A:
        delegates = [B(), C()]
        @delegate
        def f(self):
            pass
        @delegate
        def h(self):
            pass
        @delegate
        def g(self):
            pass
        @delegate
        def i(self):
            pass
    test.eq(30, A().f())

