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


class Defer:
    def __init__(self, parent, i):
        self.i = i
        self.parent = parent

    def lookup(self, name):
        for this in self.parent.delegatees[self.i:]:
            if handler := getattr(this, name, None):
                #print("   using", this.__class__.__qualname__, "for", name, handler)
                assert handler not in locals('__handler__'), f"Loop detected in {handler.__qualname__}."
                return handler
        else:
            seen = ', '.join(sorted(d.__class__.__qualname__ for d in self.parent.delegatees))
            raise AttributeError(f"{name!r} not found in: [{seen}]")

    def __getattr__(self, name):
        if name not in self.parent.delegated:
            raise AttributeError(f"'{name}' not marked for delegation")
        #print(" --- lookup", name)
        handler = self.lookup(name)
        @functools.wraps(handler)
        def delegatee(*args, **kwargs):
            __handler__ = handler
            return handler(self.parent, *args, **kwargs)
        return delegatee


class Delegate:
    """ Allows for methods to be delegated to other objects """

    delegated = ()
    delegatees = ()


    @property
    def next(self):
        top = next(locals('__handler__'), None)
        i = self.delegatees.index(top.__self__) + 1 if top else 0
        #print("last caller:", top.__class__.__qualname__, i)
        return Defer(self, i)


    def __getattr__(self, name):
        return getattr(Defer(self, 0), name)


    def delegate(self, name, *args, **kwargs):
        delegatee = self.__getattr__(name)
        return delegatee(*args, **kwargs)


    def add_delegatee(self, *delegatees, position=0):
        if 'delegatees' not in self.__dict__:
            self.delegatees = list(self.delegatees)
        for d in delegatees:
            if d.__class__ in (x.__class__ for x in self.delegatees):
                raise RuntimeError(f'Duplicate delegatee class: {d.__class__.__qualname__}.')
            self.delegatees.insert(position, d)


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
            return self.next.f()
    a = A()
    class B(Delegate):
        delegated = ('f',)
        delegatees = (a,)
    with test.raises(AttributeError, f"'f' not found in: [{A.__qualname__}]"):
        B().f()


@test
def delegation_loop_back_forth():
    class A:
        def f(this, self):
            return self.next.f()
    a = A()
    class B:
        def f(this, self):
            return self.next.f()
    b = B()
    class C(Delegate):
        delegated = {'f'}
        delegatees = (a, b)
    with test.raises(
            AttributeError,
            f"'f' not found in: [{A.__qualname__}, {B.__qualname__}]"):
        C().f()


#@test
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
def use_explicit_delegation():
    class A:
        def f(this, self, name, msg='bye'):
            return f"Hello {name}, {msg}!"
    class D(Delegate):
        delegated = ('f',)
        delegatees = (A(),)
        def f(self, name, msg):
            return self.delegate('f', name, msg=msg)
    test.eq("Hello Pite, go!", D().f('Pite', msg='go'))


@test
def check_for_duplicates():
    class A:
        pass
    class B(Delegate):
        pass
    b = B()
    b.add_delegatee(A())
    with test.raises(RuntimeError, f"Duplicate delegatee class: {A.__qualname__}."):
        b.add_delegatee(A())


@test
def only_look_up():
    class A:
        def f(this, self):
            return "A" + self.next.g()
        def h(this, self):
            return "H"
    class B:
        def g(this, self):
            return "B" + self.next.f()
    class C:
        def f(this, self):
            return 'C.f'
        def g(this, self):
            return 'C' + self.h()  # we will still be able to reach h in A
    class D(Delegate):
        delegated = 'fgh'
        delegatees = (A(), B(), C())
    d = D()
    D.delegatees = (B(), A(), C())
    test.eq('ACH', d.f())
