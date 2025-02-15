
import clingo
SymbolType = clingo.SymbolType

import selftest
test = selftest.get_tester(__name__)

class RuleCollector:

    def __init__(self):
        self.symbols = {}
        self.index = {}

    def output_atom(self, symbol, atom):
        if symbol.name == 'quote':
            self.symbols[atom] = symbol

    def rule(self, choice, heads, body):
        for atom in heads:
            self.index[atom] = (choice, tuple(heads), tuple(body))
        for atom in body:
            self.index[atom] = (choice, tuple(heads), tuple(body))

    def __getattr__(self, name):
        def f(*a, **k):
            #print(f"LOOKUP: {name}({a}, {k})")
            pass
        return f

def reified_rules(asp):
    rc = RuleCollector()
    control = clingo.Control(["--warn", "no-atom-undefined", "--preserve-facts=symtab"])
    control.register_observer(rc, replace=True)
    control.add(asp)
    control.ground()

    def quote(symbol):
        if symbol.type == SymbolType.Function:
            name = symbol.name
            arguments = symbol.arguments
            if name == 'quote':
                name, *arguments = arguments
                name = quote(name)
            elif name == 'var':
                name, *arguments = arguments
                name = name.string
            if arguments:
                arguments = map(quote, arguments)
                return f"{name}({','.join(arguments)})"
            return str(name)
        return str(symbol)

    get = rc.symbols.__getitem__
    done = set()
    for atom in rc.symbols:
        rule = rc.index[atom]
        if rule not in done:
            done.add(rule)
            choice, heads, body = rule
            head = '; '.join(quote(get(h)) for h in heads)
            body = '; '.join(quote(get(b)) for b in body)
            if body:
                yield f"{head} :-\n  {body}."
            else:
                yield f"{head}."


def test_reified_rules(asp, rules):
    test.eq(rules.strip(), '\n'.join(reified_rules(asp)), diff=test.diff)

@test
def no_rules():
    test_reified_rules("", "")

@test
def noop_rule():
    test_reified_rules("quote(a).", "a.")

@test
def simple_quote():
    test_reified_rules("""
        sein(7; 9).
        def_input(S, a, "IN-A")  :-  sein(S).
        def_input(S, b, "IN-B")  :-  sein(S).
        input(0, S, F) :- def_input(S, F, _).
        quote(F, 0, var("S"))  :-  quote(input(var("S"), F)),  input(0, S, F).
        #external quote(input(var("S"), F))  :  input(0, S, F).
        """, """
a(0,S) :-
  input(S,a).
b(0,S) :-
  input(S,b).""")
    
