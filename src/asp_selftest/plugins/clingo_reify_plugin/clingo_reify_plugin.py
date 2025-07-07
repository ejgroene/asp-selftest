import sys
import clingo
import pathlib

from .asputil import is_tuple, is_function, mk_symbol, mk_theory_atom
from ..misc import write_file, create_control, list_symbols

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


def clingo_reify_plugin(
        next,
        on_rule=lambda _:None,
        parts=(('base', ()),),
        context=None,
        arguments=(),
        **etc):
    """ Plugin turning rule predicates into reallified rules and adds them to the control."""

    logger, _load, ground, solve = next(parts=parts, context=context, arguments=arguments, **etc)  # test **etc

    def load(control, files):
        reground = True
        rules_added = set()

        while reground:
            reground = False
            sub_control = create_control(arguments=[*arguments, '--warn', 'no-atom-undefined'], **etc)
            _load(sub_control, files)
            
            for rule in rules_added:
                sub_control.add(rule)
            ground(sub_control, parts=parts, context=context)
                        
            for rule in reified_rules(sub_control):
                if rule not in rules_added:
                    rules_added.add(rule)
                    sub_control.add(rule)
                    on_rule(rule)
                    reground = True
                                
        _load(control, files)
                    
        for rule in rules_added:
            control.add(rule)

    return logger, load, ground, solve


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
    """ Reads rule predicates from the control and returns reified ASP rules. """

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


# BELOW SOME TESTS FOR INSTANTIATING RULES

def test_reified_rules(asp, reified, **etc):
    """ Helper for testing reified_rules. """
    if "&rule" in asp:
        asp += f'#include "{THEORY_FILE}".\n'
    control = clingo.Control(arguments=['--warn', 'no-atom-undefined'])
    control.add(asp)
    control.ground(**etc)
    new_rules = reified_rules(control)
    test.eq(reified.strip(), ''.join(new_rules).strip())
    return control


@test
def simple_fact_predicate():
    test_reified_rules(
"""
def(f(42)).
rule(A) :- def(A).
""", """
#external f(42).
""")


@test
def simple_fact_theory():
    test_reified_rules(
"""
def(f(42)).
&rule(A) :- def(A).
""", """
#external f(42).
""")


@test
def simple_rule(stderr):
    test_reified_rules(
"""
rule(f(41), g(42)).
b.
g(42) :- b.
c :- f(41).
""", """
f(41) :- g(42).
""")
    test.eq('', stderr.getvalue())


@test
def rule_with_condition():
    test_reified_rules(
"""
&rule(head(41)) { body0(42);  body1(N) : N=43..44 }.
""", """
head(41) :- body0(42), body1(43), body1(44).
""")


@test
def head_variable_theory():
    test_reified_rules(
"""
step(stuur(links)).
&rule(A) { body0(42) }  :-  step(A).
""", """
stuur(links) :- body0(42).
""")


@test
def head_variable_predicate():
    test_reified_rules(
"""
step(stuur(links)).
rule(A, body0(42))  :-  step(A).
""", """
stuur(links) :- body0(42).
""")


@test
def head_function():
    test_reified_rules(
"""
define(stuur).
rule((F), body0(42))  :-  define(F).
""", """
stuur :- body0(42).
""")


@test
def head_function_with_arg():
    test_reified_rules(
"""
define(stuur(links)).
rule((F), body0(42))  :-  define(F).
""", """
stuur(links) :- body0(42).
""")


@test
def head_function_with_additional_args():
    test_reified_rules(
"""
define(stuur(links, now)).
rule((F, 2, 3), body0(42))  :-  define(F).
""", """
stuur(2,3,links,now) :- body0(42).
""")


@test
def head_function_with_string():
    test_reified_rules(
"""
rule(("aap", 2, 3), body0(42)).
""", """
aap(2,3) :- body0(42).
""")


@test
def head_function_with_symbol():
    test_reified_rules(
"""
rule((aap, 2, 3), body0(42)).
""", """
aap(2,3) :- body0(42).
""")


@test
def tuples_in_theory():
    test_reified_rules(
"""
&rule((a, 1, 2)) { (b, 3),  (c, 4),  d(5) }.
""", """
a(1,2) :- b(3), c(4), d(5).
""")


@test
def reify_with_context(stderr):
    class Context:
        @staticmethod
        def zeep():
            return clingo.String("sop")
    control = test_reified_rules("""
                         b(@zeep).
                         a.
                         rule(geel, a).
                         """,
                         "geel :- a.",
                         context=Context())
    symbols = {str(sa.symbol) for sa in control.symbolic_atoms}
    test.contains(symbols, 'b("sop")')


# BELOW SOME TESTS FOR THE PLUGIN

def test_reify_plugin(tmp_path, code, rules, trace=lambda _:None, arguments=(), **etc):
    """ Helper for testing the plugin. """
    f = write_file(tmp_path/'f.lp', code)
    def next_plugin(**etc):
        def load(control, files):
            trace(('load', control, files))
            for f in files:
                control.load(f)
        def ground(control, **etc):
            trace(('ground', control, etc))
            control.ground(**etc)
        return None, load, ground, None
    new_rules = set()
    _, load, ground, _ = clingo_reify_plugin(next_plugin, on_rule=new_rules.add, arguments=arguments, **etc)
    control = clingo.Control(arguments=arguments)
    load(control, (f,))
    test.eq(rules, new_rules)
    ground(control, **etc)
    return control, ground


@test
def reify_plugin_basics(tmp_path):
    trace = []
    control, ground = test_reify_plugin(tmp_path, "b. rule(a, b).", {"a :- b.\n"}, trace.append)

    trace = iter(trace) 
    l, c0, f = next(trace)  # test if it uses new control with next_plugin for load
    test.eq('load', l)
    test.ne(control, c0)
    test.eq(1, len(f))
    test.endswith(f[0], '/f.lp')

    g, c1, etc = next(trace)  # test if it uses new control with next_plugin for ground
    test.eq('ground', g)
    test.ne(control, c1)
    test.eq(c0, c1)
    test.eq((('base', ()),), etc['parts'])
    test.eq(None, etc['context'])

    l, c0, f = next(trace)  # second load
    test.eq('load', l)
    test.ne(control, c0)
    test.eq(1, len(f))
    test.endswith(f[0], '/f.lp')

    g, c2, etc = next(trace)  # second ground for ensuring end of propagation
    test.eq('ground', g)
    test.ne(control, c2)
    test.eq(c0, c2)
    test.eq((('base', ()),), etc['parts'])
    test.eq(None, etc['context'])

    l, c2, f = next(trace)  # test if is finally load the code into our control
    test.eq('load', l)
    test.eq(control, c2)
    test.eq(1, len(f))
    test.endswith(f[0], '/f.lp')

    ground(control)
    test.eq({'a', 'b', 'rule(a,b)'}, {str(a.symbol) for a in control.symbolic_atoms})
    



@test
def reify_until_done(tmp_path):
    control, _ = test_reify_plugin(tmp_path,
    f'#include "{THEORY_FILE}".'"""
    a.
    &rule(b) { a }.
    &rule(c) {} :- b.  % not instantiated until b is True
    """,
    {'#external c.\n', 'b :- a.\n'})
    test.eq({'a', 'b', 'c'}, {str(a.symbol) for a in control.symbolic_atoms})


@test
def reify_with_disappering_atoms(stderr, tmp_path):
    control, _ = test_reify_plugin(tmp_path, """
            a.
            none(notgeel) :-  not geel.  % these cannot
            none(geel)    :-  geel.      % both be true
            rule(geel, a).
            """, {
            'geel :- a.\n'
            })
    symbols = {str(sa.symbol) for sa in control.symbolic_atoms}
    test.contains(symbols, 'none(geel)')
    test.comp.contains(symbols, 'none(notgeel)')


@test
def reify_with_disappering_atoms_in_different_programs(stderr, tmp_path):
    def reify(program_name):
        parts = (('base', ()), (program_name, ()))
        asp_code = """
            none(notgeel) :-  not geel.
            none(geel)    :-  geel.
            rule(geel, a).
            #program test_a.
            a.
            #program test_not_a.
            """
        control, ground = test_reify_plugin(
            tmp_path,
            asp_code,
            {"geel :- a.\n"}, 
            parts=parts)
        ground(control, parts=parts, context=None)
        return {str(sa.symbol) for sa in control.symbolic_atoms}

    symbols = reify('test_a')
    test.contains(symbols, 'none(geel)')
    test.comp.contains(symbols, 'none(notgeel)')

    symbols = reify('test_not_a')
    test.contains(symbols, 'none(notgeel)')
    test.comp.contains(symbols, 'none(geel)')


@test
def reify_with_context_in_plugin(tmp_path):
    class Context:
        @staticmethod
        def zeep():
            return clingo.String("sop")
    control, _ = test_reify_plugin(tmp_path, """
                         b(@zeep).
                         a.
                         rule(geel, a).
                         """,
                         {"geel :- a.\n"},
                         context=Context())
    symbols = {str(sa.symbol) for sa in control.symbolic_atoms}
    test.contains(symbols, 'b("sop")')


@test
def use_proper_logger(tmp_path):
    trace = {}
    def my_logger(code, message):
        trace[code] = message
    try:
        test_reify_plugin(tmp_path, "a", {}, logger=my_logger)
    except RuntimeError as e:
        test.eq('parsing failed', str(e))
    finally:
        code, message = next(iter(trace.items()))
        test.eq(clingo.MessageCode.RuntimeError, code)
        test.endswith(message, " error: syntax error, unexpected EOF\n")


@test
def pass_arguments_properly(tmp_path):
    control, _ = test_reify_plugin(tmp_path, "a(1). a(1/0).", set(), arguments=['--warn', 'no-operation-undefined'])
    test.eq(['a(1)'], list_symbols(control))


@test
def pass_context_properly(tmp_path):
    class Context:
        def f(self):
            return clingo.Number(42)
    control, _ = test_reify_plugin(tmp_path, "a(@f()).", set(), context=Context())
    test.eq(['a(42)'], list_symbols(control))
