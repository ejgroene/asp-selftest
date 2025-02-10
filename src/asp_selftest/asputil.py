import collections
import clingo
import clingo.ast
import contextlib

import selftest
test = selftest.get_tester(__name__)


""" This module contains ASP-specific utilities for dealing with various
    clingo data representations of similar concepts such as Symbols, 
    Functions, String etc.
    The same functions work for (but check!) for multiple representations:

     - ground symbols (clingo.symbol.Symbol etc)      (most)
     - parser symbols (clingo.ast.SymbolicAtom etc)   (many)
     - theory symbols (clingo.theory.TheoryAtom etc)  (few)
 """

A_THEORY = '#theory a { t{}; &p/1: t, head}.' # just a theory for testing


def is_ast(obj):
    return isinstance(obj, clingo.ast.AST)


class Literal(collections.namedtuple('Literal', ['sign', 'symbol', 'type'])):
    def __str__(self):
        return f"not {self.symbol}" if self.sign else str(self.symbol)


def is_literal(obj):
    if is_ast(obj):
        return obj.ast_type == clingo.ast.ASTType.Literal
    if isinstance(obj, Literal):
        return True


def is_function(obj, name=None):
    if is_ast(obj):
        return obj.ast_type == clingo.ast.ASTType.Function and (name is None or obj.name == name)
    if is_literal(obj):
        return obj.type == clingo.SymbolType.Function and (name is None or obj.symbol.name == name)
    if is_theory_term(obj):
        assert name is None
        return obj.type == clingo.TheoryTermType.Function
    return obj.type == clingo.SymbolType.Function and (name is None or obj.name == name)


def is_tuple(s):
    if isinstance(s, clingo.TheoryTerm):
        return s.type == clingo.TheoryTermType.Tuple
    return is_function(s, '')


def is_number(symbol):
    return symbol.type == clingo.SymbolType.Number


def is_string(symbol):
    if isinstance(symbol, clingo.TheoryTerm):
        s = symbol
        return s.type == clingo.TheoryTermType.Symbol and s.name[0] == s.name[-1] == '"'
    return symbol.type == clingo.SymbolType.String


def is_symbol(symbol):
    return symbol.type == clingo.TheoryTermType.Symbol


def is_variable(ast):
    return ast.ast_type == clingo.ast.ASTType.Variable


def is_symbolicterm(ast):
    return ast.ast_type == clingo.ast.ASTType.SymbolicTerm


def is_conditional(ast):
    return ast.ast_type == clingo.ast.ASTType.ConditionalLiteral


def is_disjunction(ast):
    return ast.ast_type == clingo.ast.ASTType.Disjunction


def is_positive(ast):
    if is_ast(ast):
        lit = ast.literal if is_conditional(ast) else ast
        return lit.sign == 0
    return not ast.sign


def is_binaryoperation(ast):
    return ast.ast_type == clingo.ast.ASTType.BinaryOperation


def is_minusoperation(ast):
    return is_unaryoperation(ast) and ast.operator_type == clingo.ast.UnaryOperator.Minus


def is_unaryoperation(ast):
    return ast.ast_type == clingo.ast.ASTType.UnaryOperation


def mk_ast(lit):
    if is_ast(lit):
        return lit
    source_rules = []
    def cb(ast):
        if ast.ast_type == clingo.ast.ASTType.Rule:
            source_rules.append((ast.head, ast.body))
    clingo.ast.parse_string(lit+'.', cb)
    return source_rules[0][0]


mk_symbol = clingo.parse_term


def mk_literal(literal):
    sign = literal.startswith('not')
    symbol = mk_symbol(literal[4 if sign else 0:])
    return Literal(sign=sign, symbol=symbol, type=symbol.type)


@contextlib.contextmanager
def mk_theory_atom(asp, theory):
    c = clingo.Control()
    c.add(theory)
    c.add(asp)
    c.ground()
    yield next(c.theory_atoms)


def is_theory_term(symbol):
    return isinstance(symbol, clingo.TheoryTerm)


@test
def simple_terms():
    time = mk_literal('time')
    test.eq("time", time.symbol.name)
    test.eq(clingo.SymbolType.Function, time.symbol.type)
    test.eq('time', str(time))
    test.truth(is_function(time))
    test.truth(is_function(time, name='time'))
    test.not_ (is_function(time, name='fire'))
    test.truth(is_function(mk_literal('time(3)')))
    test.truth(is_function(mk_literal('time(3)'), name='time'))


@test
def simple_numbers():
    time = mk_literal('23')
    test.eq(clingo.SymbolType.Number, time.type)
    test.eq(23, time.symbol.number)
    test.truth(is_number(time))
    test.not_ (is_function(time))
    test.not_ (is_string(time))


@test
def simple_strings():
    time = mk_literal('"24"')
    test.eq(clingo.SymbolType.String, time.type)
    test.eq("24", time.symbol.string)
    test.truth(is_string(time))
    test.not_ (is_function(time))
    test.not_ (is_number(time))


@test
def is_string_theory():
    with mk_theory_atom('&p("aap").', A_THEORY) as ta:
        test.truth(is_string(ta.term.arguments[0]))



@test
def function_wit_arguments():
    time = mk_literal('time(24, "H")')
    test.eq('time(24,"H")', str(time))
    test.truth(is_function(time))
    test.not_ (time.sign)
    test.eq("time", time.symbol.name)
    test.truth(is_function(time))
    args = time.symbol.arguments
    test.truth(is_number(args[0]))
    test.truth(is_string(args[1]))


@test
def some_asts_and_their_structure():
    test.truth(is_literal(mk_ast('bool')))
    test.truth(is_literal(mk_ast('bool(1)')))
    test.truth(is_literal(mk_ast('bool(a, 1)')))
    l = mk_ast('not bool(a, A, 1, "A", f(a))')
    l2 = mk_ast(l)
    test.eq(l, l2)
    test.truth(is_literal(l))
    b = l.atom.symbol
    test.truth(is_function(b, name='bool'))
    test.not_ (is_function(b, name='loob'))
    a, A, one, strA, fa = b.arguments
    test.truth(is_symbolicterm(a))
    test.truth(is_function(a.symbol))
    test.eq('a', a.symbol.name)
    test.truth(is_variable(A))
    test.eq('A', A.name)
    test.truth(is_symbolicterm(one))
    test.truth(is_number(one.symbol))
    test.truth(is_symbolicterm(strA))
    test.truth(is_string(strA.symbol))
    test.truth(is_function(fa))


@test
def conditional_positive_literals():
    d0 = mk_ast('b : c')
    test.truth(is_disjunction(d0))
    test.not_ (is_conditional(d0))
    c0 = d0.elements[0]
    test.truth(is_conditional(c0))
    test.not_ (is_disjunction(c0))
    test.truth(is_positive(c0))
    l0 = c0.literal
    test.truth(is_literal(l0))
    test.not_ (is_conditional(l0))
    test.not_ (is_disjunction(l0))
    test.truth(is_positive(l0))


@test
def conditional_negative_literals():
    d1 = mk_ast('not b : c')
    test.truth(is_disjunction(d1))
    test.not_ (is_conditional(d1))
    c1 = d1.elements[0]
    test.truth(is_conditional(c1))
    test.not_ (is_disjunction(c1))
    test.not_ (is_positive(c1))
    l1 = c1.literal
    test.truth(is_literal(l1))
    test.not_ (is_conditional(l1))
    test.not_ (is_disjunction(l1))
    test.not_ (is_positive(l1))


@test
def pos_and_neg_literal_symbol():
    posA = mk_literal('a')
    test.truth(is_literal(posA))
    test.truth(is_positive(posA))
    negA = mk_literal('not a')
    test.eq('not a', str(negA))
    test.truth(is_literal(negA))
    test.not_(is_positive(negA))


@test
def symbolic_atoms():
    l = mk_literal('not b(0,e)')
    test.eq(True, l.sign)
    test.eq(mk_literal('b(0,e)').symbol, l.symbol)


@test
def unary_op_and_minus():
    u = mk_ast("f(-A)").atom.symbol.arguments[0]
    test.truth(is_unaryoperation(u))
    test.eq(clingo.ast.UnaryOperator.Minus, u.operator_type)
    test.truth(is_minusoperation(u))
    u = mk_ast("f(|A|)").atom.symbol.arguments[0]
    test.truth(is_unaryoperation(u))
    test.eq(clingo.ast.UnaryOperator.Absolute, u.operator_type)
    test.not_(is_minusoperation(u))
    u = mk_ast("f(~A)").atom.symbol.arguments[0]
    test.truth(is_unaryoperation(u))
    test.eq(clingo.ast.UnaryOperator.Negation, u.operator_type)
    test.not_(is_minusoperation(u))


@test
def bin_op():
    b = mk_ast("f(1+2)").atom.symbol.arguments[0]
    test.truth(is_binaryoperation(b))


@test
def is_tuple_with_theory():
    test.truth(is_tuple(mk_literal('(1,2,3)')))
    with mk_theory_atom('&p((1,2,3)).', A_THEORY) as ta:
        test.truth(is_tuple(ta.term.arguments[0]))

