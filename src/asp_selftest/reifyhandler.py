import clingo
import pathlib
import sys

from .asputil import is_tuple, is_function, is_string, is_symbol, mk_symbol, mk_theory_atom, is_theory_term


from .syntaxerrorhandler import ground_exc


import selftest
test = selftest.get_tester(__name__)


""" Support for reification of rules in ASP code.
    It supports predicates and a special theory:

      rule(<head>, <body0>, ... <bodyN>).
      &rule(<head>) { body0; ...; <bodyN>).

    The predicate form can be handy when the program must remain ASP-compatible.
    Be careful: it can be used in both head and body, while only head makes sense.
    The theory form is restricted to heads and can handle conditional bodies (variable bodies).
    The latter is the prefered method.

    A tuple (<name>, <arg0>, ..., <argN>) if will transform to:

      <name>(<arg0>, ..., <argN>).

    When <name> is itself a function, its arguments are prepended to <arg0>..<argN>.
    Thus, (name(a), b, c) becomes name(a, b, c).
"""

# ASP #theory defining the symtax of the &reify/1 atom
MY_PATH = pathlib.Path(__file__).resolve()
THEORY_PATH = MY_PATH.parent
THEORY_FILE = MY_PATH.with_name('reify.lp')


def asp_reify(code):
    """ support for reifying a snippet of ASP (entry point asp-reify)"""
    # TODO make use of ground_exc
    control = clingo.Control(arguments=['--warn', 'no-atom-undefined'])
    control.add(code)
    control.ground()
    return reified_rules(control)


class ReifyHandler:

    def load(this, self, control, parameters, piggies=None):
        parts = parameters.get('parts', None)
        if not parts:
            parts = [('base', ())] # + [(p, ()) for p in self.programs or []]
        ast = parameters['ast']

        rules_added = set()
        ground = True
        while ground:
            tmpcontrol = self.control(parameters)
            args = ()
            tmpcontrol = clingo.Control(args, logger=self.logger, message_limit=1)
            self.next.load(tmpcontrol, parameters)
            self.next.ground(tmpcontrol, parameters)
            ground = False
            for rule in reified_rules(tmpcontrol):
                if rule not in rules_added:
                    print(rule, file=open('reified_rules.log', 'a'))
                    clingo.ast.parse_string(rule, ast.append)
                    rules_added.add(rule)
                    ground = True
        self.next.load(control, parameters)


    def logger(this, self, code, message):
        if code == clingo.MessageCode.AtomUndefined:
            return True


def to_symbol(theory_term):
    if isinstance(theory_term, clingo.TheoryTerm):
        return clingo.parse_term(str(theory_term))
    return theory_term


def make_function(arguments):
    name, *args = arguments
    #assert is_string(name) or is_function(name), \
    #       f"First element '{name}' must be a name or function {name.type}"
    try:
        args = args + name.arguments # + args
    except RuntimeError:
        pass
    try:
        name = name.name
    except RuntimeError:
        name = str(name)[1:-1]
    args = [to_symbol(a) for a in args]
    return clingo.Function(name, args)


@test
def make_function_from_symbols():
    T = "#theory x{t{};&sym/1:t,head;&sym/2:t,head}."
    test.eq('naam', str(make_function([mk_symbol('naam')])))
    test.eq('naam(a)', str(make_function([mk_symbol('naam'), mk_symbol('a')])))
    test.eq('naam(b,a)', str(make_function([mk_symbol('naam(a)'), mk_symbol('b')])))

    with mk_theory_atom('&sym(naam).', T) as a:
        test.eq('naam', str(make_function(a.term.arguments)))
    with mk_theory_atom('&sym(naam(a)).', T) as a:
        test.eq('naam(a)', str(make_function(a.term.arguments)))
    with mk_theory_atom('&sym(naam(a), b).', T) as a:
        test.eq('naam(b,a)', str(make_function(a.term.arguments)))


def reified_rules(control):

    def reifies():
        by_signature = control.symbolic_atoms.by_signature
        for sa in by_signature('rule', 1):
            yield sa.symbol, sa.symbol.arguments
        for sa in by_signature('rule', 2):
            yield sa.symbol, sa.symbol.arguments
        for ta in control.theory_atoms:
            term = ta.term
            if term.name.startswith('rule'):
                yield ta, term.arguments + ta.elements

    for function, arguments in reifies():
        assert arguments, f"'{function}' must at least have one argument"
        head, *body = arguments
        if is_tuple(head):
            head = make_function(head.arguments)

        if body:
            if isinstance(body[0], clingo.TheoryElement):
                new_body = []
                for b in body:
                    for t in b.terms:
                        if is_tuple(t):
                            f = make_function(t.arguments)
                            new_body.append(f)
                        else:
                            new_body.append(t)
                body = new_body
            yield f"{head} :- {', '.join(map(str, body))}.\n"
        else:
            yield f"#external {head}.\n"


def test_reify(asp, reified, parts=None, context=None):
    if "&rule" in asp:
        asp += f'#include "{THEORY_FILE}".\n'
    control = ground_exc(asp, handlers=(ReifyHandler(),), parts=parts, context=context)
    new_rules = reified_rules(control)
    test.eq(reified.strip(), ''.join(new_rules).strip())
    return control


@test
def simple_fact_predicate():
    test_reify(
"""
def(f(42)).
rule(A) :- def(A).
""", """
#external f(42).
""")


@test
def simple_fact_theory():
    test_reify(
"""
def(f(42)).
&rule(A) :- def(A).
""", """
#external f(42).
""")


@test
def simple_rule():
    test_reify(
"""
rule(f(41), g(42)).
b.
g(42) :- b.
c :- f(41).
""", """
f(41) :- g(42).
""")


@test
def rule_with_condition():
    test_reify(
"""
&rule(head(41)) { body0(42);  body1(N) : N=43..44 }.
""", """
head(41) :- body0(42), body1(43), body1(44).
""")


@test
def head_variable_theory():
    test_reify(
"""
step(stuur(links)).
&rule(A) { body0(42) }  :-  step(A).
""", """
stuur(links) :- body0(42).
""")


@test
def head_variable_predicate():
    test_reify(
"""
step(stuur(links)).
rule(A, body0(42))  :-  step(A).
""", """
stuur(links) :- body0(42).
""")


@test
def head_function():
    test_reify(
"""
define(stuur).
rule((F), body0(42))  :-  define(F).
""", """
stuur :- body0(42).
""")


@test
def head_function_with_arg():
    test_reify(
"""
define(stuur(links)).
rule((F), body0(42))  :-  define(F).
""", """
stuur(links) :- body0(42).
""")


@test
def head_function_with_additional_args():
    test_reify(
"""
define(stuur(links, now)).
rule((F, 2, 3), body0(42))  :-  define(F).
""", """
stuur(2,3,links,now) :- body0(42).
""")


@test
def head_function_with_string():
    test_reify(
"""
rule(("aap", 2, 3), body0(42)).
""", """
aap(2,3) :- body0(42).
""")


@test
def head_function_with_symbol():
    test_reify(
"""
rule((aap, 2, 3), body0(42)).
""", """
aap(2,3) :- body0(42).
""")


@test
def tuples_in_theory():
    test_reify(
"""
&rule((a, 1, 2)) { (b, 3),  (c, 4),  d(5) }.
""", """
a(1,2) :- b(3), c(4), d(5).
""")


def quick_parse_asp(code):
    ast = []
    clingo.ast.parse_string(code, ast.append, logger=print)
    return ast


@test
def reify_until_done():
    control = test_reify(
    f'#include "{THEORY_FILE}".'"""
    a.
    &rule(b) { a }.
    &rule(c) {} :- b.  % not instantiated until b is True
    """,
    "#external c.\nb :- a.")
    test.eq({'a', 'b', 'c'}, {str(a.symbol) for a in control.symbolic_atoms})


@test
def reify_with_disappering_atoms(stderr):
    control = test_reify("""
            a.
            none(notgeel) :-  not geel.  % these cannot
            none(geel)    :-  geel.      % both be true
            rule(geel, a).
            """, """
            geel :- a.
            """)
    symbols = {str(sa.symbol) for sa in control.symbolic_atoms}
    test.contains(symbols, 'none(geel)')
    test.comp.contains(symbols, 'none(notgeel)')


@test
def reify_with_disappering_atoms_in_different_programs(stderr):
    def reify(program_name):
        asp_code = """
            none(notgeel) :-  not geel.
            none(geel)    :-  geel.
            rule(geel, a).
            #program test_a.
            a.
            #program test_not_a.
            """
        control = test_reify(asp_code, "geel :- a.", parts=[('base', ()), (program_name, ())])
        return {str(sa.symbol) for sa in control.symbolic_atoms}

    symbols = reify('test_a')
    test.contains(symbols, 'none(geel)')
    test.comp.contains(symbols, 'none(notgeel)')

    symbols = reify('test_not_a')
    test.contains(symbols, 'none(notgeel)')
    test.comp.contains(symbols, 'none(geel)')


@test
def reify_with_context(stderr):
    class Context:
        @staticmethod
        def zeep():
            return clingo.String("sop")
    control = test_reify("""
                         b(@zeep).
                         a.
                         rule(geel, a).
                         """,
                         "geel :- a.",
                         context=Context())
    symbols = {str(sa.symbol) for sa in control.symbolic_atoms}
    test.contains(symbols, 'b("sop")')

