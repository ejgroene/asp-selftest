import sys
import clingo
import functools
import inspect
import traceback


import selftest
test = selftest.get_tester(__name__)



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



class Delegate:
    """ Allows for methods to be delegated to other objects """

    delegated = ()
    delegatees = ()

    def __getattr__(self, name):
        if name not in self.delegated:
            raise AttributeError(f"'{name}' not marked for delegation")
        def delegatee(*args, **kwargs):
            for this in self.delegatees:
                if handler := getattr(this, name, None):
                    if handler in locals('handler'):
                        continue
                    return handler(self, *args, **kwargs)
            seen = ', '.join(sorted(set(l.__qualname__ for l in locals('handler'))))
            raise AttributeError(f"{name!r} not found in: [{seen}]")
        return delegatee


    def add_delegatee(self, *delegatees):
        if 'delegatees' not in self.__dict__:
            self.delegatees = list(self.delegatees)
        for d in delegatees:
            self.delegatees.insert(0, d)


@test
def delegation_not_mentioned():
    class B(Delegate):
        pass
    with test.raises(AttributeError, "'f' not marked for delegation"):
        B().f()


@test
def delegation_none():
    class B(Delegate):
        delegated = ['f']
    with test.raises(AttributeError, "'f' not found in: []"):
        B().f()


@test
def delegation_one():
    class A:
        def f(this, self):
            return this, self
    a = A()
    class B(Delegate):
        delegated = ['f']
        delegatees = (a,)
    b = B()
    test.eq((a, b), b.f())


@test
def delegation_loop():
    class A:
        def f(this, self):
            return self.f()
    a = A()
    class B(Delegate):
        delegated = ('f',)
        delegatees = (a,)
    with test.raises(AttributeError, "'f' not found in: [delegation_loop.<locals>.A.f]"):
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
    class C(Delegate):
        delegated = {'f'}
        delegatees = (a, b)
    with test.raises(
            AttributeError,
            "'f' not found in: [delegation_loop_back_forth.<locals>.A.f, delegation_loop_back_forth.<locals>.B.f]"):
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
    class A(Delegate):
        delegated = ['f', 'h', 'g', 'i']
        delegatees = [B(), C()]
    test.eq(30, A().f())


@test
def seperate_delegation():
    class A:
        def f(this, self):
            return 'A42'
    class B:
        def f(this, self):
            return 'B42'
    class C(Delegate):
        delegated = ['f']
    c1 = C()
    c2 = C()
    c1.add_delegatee(A())
    c2.add_delegatee(B())
    test.eq('A42', c1.f())
    test.eq('B42', c2.f())

@test
def add_delegatees():
    class A:
        def f(this, self):
            return 'A'
    class B:
        def g(this, self):
            return 'B'
    class C:
        def h(this, self):
            return 'C'
    class D(Delegate):
        delegatees = (A(),)
        delegated = ['f', 'h', 'g', 'i']
    d1 = D()
    d2 = D()
    d1.add_delegatee(B(), C())
    test.eq('A', d1.f())
    test.eq('B', d1.g())
    test.eq('C', d1.h())
    test.eq('A', d2.f())
    with test.raises(AttributeError):
        d2.g()
    with test.raises(AttributeError):
        d2.h()


@test
def check_for_duplicates():
    pass
