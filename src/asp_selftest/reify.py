import tempfile
import clingo
import selftest

test = selftest.get_tester(__name__)


def tstr(l):
    return tuple(map(str,l))


def make_function(symbol):
    if symbol.type == clingo.symbol.SymbolType.Function:
        if symbol.name == 'reify':
            name, *arguments = symbol.arguments
            return clingo.symbol.Function(name.name, arguments)


def replace(symbols):
    add = False
    hs = []
    for h in symbols:
        if f := make_function(h):
            add = True
            hs.append(f)
        else:
            hs.append(h)
    return add, tuple(hs)


class Reify:

    def ground(self, prev, ctl, parts, context=None):
        ctl.add("#defined reify/1. #defined reify/2. #defined reify/3. #defined reify/4.")
        o = RuleCollector()
        ctl.register_observer(o)
        prev(ctl, parts, context)
        def get_reifies():
            symbols = {s.literal: s.symbol for s in ctl.symbolic_atoms}
            for r in o.rules:
                print(">>>", *r)
            print(symbols)
            reifies = set()
            for choice, heads, body in o.resolve(symbols.__getitem__):
                h, new_heads = replace(heads)
                b, new_body = replace(body)
                if h or b:
                    reifies.add((choice, new_heads, new_body))
            return reifies
        reifies = get_reifies()
        reified = set()
        while reifies > reified:
            with tempfile.NamedTemporaryFile(mode='w', prefix='reify-', suffix='.lp') as f:
                for choice, heads, body in reifies:
                    atom= f"{', '.join(str(h) for h in heads)}  :-  {', '.join(str(b) for b in body)}."
                    print("REIFIED:", atom)
                    f.write(atom)
                f.flush()
                ctl.load(f.name)
                prev(ctl, parts, context)
                reified = reifies
                reifies = get_reifies()

class RuleCollector:

    def __init__(self):
        self.rules = []

    def rule(self, choice, heads, body):
        self.rules.append((choice, heads, body))

    def external(self, *a):
        print("EXTERNAL:", a)

    def output_atom(self, symbol, atom):
        print("ATOM:", atom, symbol)

    def output_term(self, symbol, condition):
        print("TERM:", condition, symbol)

    def resolve(self, get):
        for choice, heads, body in self.rules:
            yield choice, [get(h) for h in heads], [get(b) for b in body]


@test
def collect_rules():
    r = RuleCollector()
    r.rule(True, [0, 1], [2, 3])
    r.rule(False, [2, 4], [1, 7])
    test.eq((True, [0, 1], [2, 3]), r.rules[0])
    test.eq((False, [2, 4], [1, 7]), r.rules[1])
    test.eq(2, len(r.rules))


@test
def resolve_symbols():
    r = RuleCollector()
    r.rule(True, [0, 1], [2, 3])
    r.rule(False, [2, 4], [1, 7])
    test.eq([(True, ['a', 'b'], ['c', 'd']), (False, ['c', 'e'], ['b', 'h'])],
            list(r.resolve({0:'a', 1:'b', 2:'c', 3:'d', 4:'e', 7:'h'}.get)))
