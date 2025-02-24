
import textwrap

import clingo
SymbolType = clingo.SymbolType

import selftest
test = selftest.get_tester(__name__)

class RuleCollector:

    def __init__(self):
        self.symbols = {}
        self.index = {}
        self.externals = set()
        self.quotes = set()
        self.rules = []

    def output_atom(self, symbol, atom):
        if symbol.name == 'quote':
            self.quotes.add(atom)
        print("SYMBOL:", atom, symbol)
        self.symbols[atom] = symbol

    def rule(self, choice, heads, body):
        print("RULE:", heads, body)
        self.rules.append((choice, tuple(heads), tuple(body)))
        for atom in heads:
            self.index[atom] = len(self.rules) -1
        for atom in body:
            self.index[atom] = len(self.rules) -1

    def substitute(self):
        for i, rule in enumerate(self.rules):
            choice, heads, body = rule
            for b in body:
                if b not in self.symbols:
                    pass

    def external(self, atom, value):
        assert value == clingo.TruthValue.False_, value
        print("EXT:", atom)
        self.externals.add(atom)

    def __getattr__(self, name):
        def f(*a, **k):
            print(f"LOOKUP: {name}({a}, {k})")
        return f


def reified_rules(asp, yield_control=False):
    rc = RuleCollector()
    control = clingo.Control(["--warn", "no-atom-undefined", "--preserve-facts=all"])
    control.register_observer(rc)
    control.add(asp)
    control.ground()

    if yield_control:
        yield control

    def quote(symbol):
        if symbol.type == SymbolType.Function:
            name = symbol.name
            arguments = symbol.arguments
            if name == 'quote':
                name, *arguments = arguments
                if name.type == SymbolType.Function and name.name == 'var':
                    raise ValueError(f"quote cannot have {name} as first argument")
                name = quote(name)
            elif name == 'var':
                name, *arguments = arguments
                name = name.string
            sign = '' if symbol.positive else '-'
            rule = f"{sign}{name}" 
            if arguments:
                arguments = map(quote, arguments)
                rule += f"({', '.join(arguments)})"
            return rule
        return str(symbol)

    get = rc.symbols.__getitem__
    done = set()
    for atom in rc.quotes:
        if atom not in rc.index:
            continue
        rulenr = rc.index[atom]
        rule = rc.rules[rulenr]
        if rule not in done:
            done.add(rule)
            print("processing rule:", rule)
            choice, heads, body = rule
            head = '; '.join(quote(get(h)) for h in heads)
            body = '; '.join(quote(get(b)) for b in body)
            if body:
                yield f"{head} :-\n  {body}."
            else:
                yield f"{head}."


def test_reified_rules(asp, rules, symbols=None):
    reified = reified_rules(asp, yield_control=bool(symbols))
    if symbols:
        control = next(reified)
    new_rules = '\n'.join(reified)
    test.eq(textwrap.dedent(rules), new_rules, diff=test.diff)
    if symbols:
        control.add(new_rules)
        control.ground()
        ground_symbols = {str(sa.symbol) for sa in control.symbolic_atoms}
        for symbol in symbols:
            test.contains(ground_symbols, symbol)


#@test
def no_nothing():
    test_reified_rules("", "")

#@test
def noop_fact():
    test_reified_rules("quote(a).", "a.", symbols=('a',))

#@test
def fact_with_function():
    test_reified_rules("quote(a(42)).", "a(42).")

#@test
def fact_with_nested_function():
    test_reified_rules("quote(a(42, b(84, c(x)))).", "a(42, b(84, c(x))).")

#@test
def fact_with_different_datatypes():
    test_reified_rules('quote(a(42, a, "X", 34, b)).', 'a(42, a, "X", 34, b).')

#@test
def fact_with_negative_datatypes():
    test_reified_rules('quote(-a(-42, -a, "-X", -34, -b)).', '-a(-42, -a, "-X", -34, -b).')

#@test
def fact_from_first_argument():
    test_reified_rules('quote(f, 42, aa).', 'f(42, aa).')

#@test
def fact_with_var():
    # Not correct ASP when used as fact, but you'll discover that later on.
    test_reified_rules('quote(f, var("A")).', 'f(A).') 

#@test
def fact_cannot_start_with_var():
    with test.raises(ValueError, 'quote cannot have var("A") as first argument'):
        test_reified_rules('quote(var("A")).', 'N/A')

#@test
def fact_in_body_cannot_start_with_var():
    with test.raises(ValueError, 'quote cannot have var("B") as first argument'):
        test_reified_rules('#external quote(var("B")). a :- quote(var("B")).', 'N/A')

#@test
def quote_in_body():
    test_reified_rules('#external quote(foo;bar). a :- quote(foo), quote(bar).', 'a :-\n  bar; foo.') 

#@test
def quote_in_body_with_variable():
    test_reified_rules("""
    #external quote(foo;bar).
    a :- quote(A).
    """, """\
    a :-
      foo.
    a :-
      bar.""") 

#@test
def external_with_quote():
    test_reified_rules('#external quote(foo).', '') 

#@test
def quote_in_body_with_var():
    test_reified_rules("""
    #external quote(foo, var("A")).
    a :- quote(foo, var("A")).
    """, """\
    a :-
      foo(A).""") 

#@test
def simple_quote():
    test_reified_rules("""
        #external quote(input(var("S"), F)) : def_input(_, F, _).
        sein(7; 9).
        def_input(S, a, "IN-A")  :-  sein(S).
        def_input(S, b, "IN-B")  :-  sein(S).
        #external input(0, S, F)  :  def_input(S, F, _).
        input(0, S, F) :- def_input(S, F, _).
        quote(F, 0, var("S"))  :-  quote(input(var("S"), F)),  def_input(_, F, _).
        """, """\
a(0, S) :-
  input(S, a).
b(0, S) :-
  input(S, b).""")
    
