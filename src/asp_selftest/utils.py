import clingo

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
