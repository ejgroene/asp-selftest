
""" Functions to runs all tests in an ASP program. """

import inspect
import clingo
import sys
import ast
import threading


# Allow ASP programs started in Python to include Python themselves.
from clingo.script import enable_python
enable_python()


def parse_signature(s):
    """
    Parse extended #program syntax using Python's parser.
    ASP #program definitions allow a program name and simple constants are arguments:

        #program p(s1,...,sn).

    where p is the program name and arguments si are constants.

    For asp-selftest, we allow atoms as arguments:
        
        #program p(a1,...,an).

    where p is the program name and arguments ai are atoms. Atoms can be functions
    with their own arguments. This allows ai to refer to other #programs arguments.
    """
    parse = lambda o: o.value if isinstance(o, ast.Constant) else \
                   (o.id, []) if isinstance(o, ast.Name) else \
                   (o.func.id, [parse(a) for a in o.args])
    return parse(ast.parse(s).body[0].value)


# We use thread locals to communicate state between python code embedded in ASP and this module here.
local = threading.local()


def register(func):
    """ Selftest uses the context for supplying the functions @all and @models to the ASP program. 
        As a result the ASP program own Python functions are ignored. To reenable these, they must
        be registered using register(func).
    """
    assert inspect.isfunction(func), f"{func!r} must be a function"
    if tester := getattr(local, 'current_tester', None):  #TODO testme hasattr iso local.current_tester
        tester.add_function(func)


class Tester:

    def __init__(self):
        self._asserts = set()
        self._anys = set()
        self._models_ist = 0
        self._models_soll = -1
        self._funcs = {}


    def all(self, *args):
        """ ASP API: add a named assert to be checked for each model """
        assrt = clingo.Function("assert", args)
        if assrt in self._asserts:
            print(f"WARNING: duplicate assert: {assrt}")
        self._asserts.add(assrt)
        return args


    def any(self, *args):
        assrt = clingo.Function("assert", args)
        if assrt in self._anys:
            print(f"WARNING: duplicate assert: {assrt}")
        self._anys.add(assrt)
        return args


    def models(self, n):
        """ ASP API: add assert for the total number of models """
        self._models_soll = n.number
        return self.all(clingo.Function("models", [n]))


    def on_model(self, model):
        """ Callback when model is found; count model and check all asserts. """
        self._models_ist += 1
        for a in set(self._anys):
            if model.contains(a):
                self._anys.remove(a)
        failures = [a for a in self._asserts if not model.contains(a)]
        if failures:
            symbols = sorted(str(s) for s in model.symbols(shown=True))
            if len(symbols) > 0:
                col_width = (max(len(w) for w in symbols)) + 2
                import shutil
                import itertools
                width, h = shutil.get_terminal_size((80, 20))
                cols = width // col_width
                modelstr = '\n'.join(
                        ''.join(s.ljust(col_width) for s in b)
                    for b in itertools.batched(symbols, max(cols, 1)))
            else:
                modelstr = "<empty>"

            raise AssertionError(f"FAILED: {', '.join(map(str, failures))}\nMODEL:\n{modelstr}")
        return model


    def report(self):
        """ When done, check assert(@models(n)) explicitly, then report. """
        assert self._models_ist == self._models_soll, f"Expected {self._models_soll} models, found {self._models_ist}."
        assert not self._anys, f"Asserts not in any model:\n{'\n'.join(str(a) for a in self._anys)}"
        return dict(asserts={str(a) for a in self._asserts}, models=self._models_ist)


    def add_function(self, func):
        self._funcs[func.__name__] = func

    
    def __getattr__(self, name):
        if name in self._funcs:
            return self._funcs[name]
        raise AttributeError(name)


def read_programs(asp_code):
    """ read all the #program parts and register their dependencies """
    lines = asp_code.splitlines()
    programs = {'base': []}
    for i, line in enumerate(lines):
        if line.strip().startswith('#program'):
            name, dependencies = parse_signature(line.split('#program')[1].strip()[:-1])
            if name in programs:
                raise Exception(f"Duplicate program name: {name!r}")
            programs[name] = dependencies
            # rewrite into valid ASP (turn functions into plain terms)
            lines[i] = f"#program {name}({','.join(dep[0] for dep in dependencies)})."
    return lines, programs


def ground_and_solve(lines, programs=(('base', ()),), observer=None, context=None, on_model=None):
    errors = []
    def warn2raise(code, msg):
        """ collect exceptions from warnings logged by Clingo """
        print(code, msg, file=sys.stderr)

        def parse_block(msg):
            """ parses location in "<block>:2:1-2: error: syntax error, unexpected EOF" """
            file, line, pos, __, msg, *more = msg.split(':', 5)
            start, end = pos.split('-')
            return file, int(line), int(start), int(end), msg.strip(), ':'.join(more)

        file, line, start, end, msg, more = parse_block(msg)
        if file == '<block>':
            srclines = lines
        else:
            # TODO TESTME
            srclines = [l.removesuffix('\n') for l in open(file).readlines()]
        snippet = [srclines] if isinstance(srclines, str) else srclines[max(0, line-5):line]

        def add_arrow(start, end):
            snippet.append(' ' * (start-1) + '^' * (end-start))

        add_arrow(start, end)

        if '<block>:' in more:
            """ possibly nested, more precise location given by Clingo """
            # TODO TESTME + if not block but file
            *code, block = more.splitlines()
            snippet.extend(code)
            file, _, start, end, msg2, __ = parse_block(block)
            add_arrow(start+2, end+2)
            snippet.append(' '*start + msg2)
        elif more:
            msg += ':' + more.replace('\n', '')

        errors.append(SyntaxError(f"in ASP code: {msg}\n{'\n'.join(snippet)}"))

    control = clingo.Control(['0'], logger=warn2raise, message_limit=1)
    if observer:
        control.register_observer(observer)
    try:
        control.add('\n'.join(lines))
        control.ground(programs, context=context)
    except RuntimeError as e:
        # we assume an corresponding log message has been recorded
        raise errors[0].with_traceback(None) from None
    if errors:
        raise errors[0]
    control.solve(on_model=on_model)
    return control


def run_tests(lines, programs):
    for prog_name, dependencies in programs.items():
        if prog_name.startswith('test'):
            tester = local.current_tester = Tester()

            def prog_with_dependencies(name, dependencies):
                yield name, [clingo.Number(42) for _ in dependencies]
                for dep, args in dependencies:
                    assert dep in programs, f"Dependency {dep} of {name} not found."
                    formal_args = programs.get(dep, [])
                    formal_names = list(a[0] for a in formal_args)
                    if len(args) != len(formal_names):
                        raise Exception(f"Argument mismatch in {prog_name!r} for dependency {dep!r}. Required: {formal_names}, given: {args}.")
                    yield dep, [clingo.Number(a) for a in args]

            to_ground = list(prog_with_dependencies(prog_name, dependencies))
            try:
                ground_and_solve(lines, to_ground, tester, tester, tester.on_model)
            except Exception as e:
                raise Exception(f"Error while running {prog_name}.") from e
            yield prog_name, tester.report()


def parse_and_run_tests(asp_code):
    lines, programs = read_programs(asp_code)
    return run_tests(lines, programs)


def run_asp_tests(*files):
    for program_file in files:
        print(f"Reading {program_file}.", flush=True)
        asp_code = open(program_file).read()
        for name, result in parse_and_run_tests(asp_code):
            asserts = result['asserts']
            models = result['models']
            print(f"ASPUNIT: {name}: ", end='', flush=True)
            print(f" {len(asserts)} asserts,  {models} model{'s' if models>1 else ''}")



import selftest
test = selftest.get_tester(__name__)


@test
def parse_some_signatures():
    test.eq(('one', []), parse_signature("one"))
    test.eq(('one', [('two', []), ('three', [])]), parse_signature("one(two, three)"))
    test.eq(('one', [('two', []), ('three', [])]), parse_signature("one(two, three)"))
    test.eq(('one', [2, 3]), parse_signature("one(2, 3)"))
    test.eq(('one', [('two', [2, ('aap', [])]), ('three', [42])]), parse_signature("one(two(2, aap), three(42))"))


@test
def read_no_programs():
    lines, programs = read_programs(""" fact. """)
    test.eq([" fact. "], lines)
    test.eq({'base': []}, programs)


@test
def read_no_args():
    lines, programs = read_programs(""" fact. \n#program a.""")
    test.eq([" fact. ", "#program a()."], lines)
    test.eq({'base': [], 'a': []}, programs)


@test
def read_one_arg():
    lines, programs = read_programs(""" fact. \n#program a. \n #program b(a). """)
    test.eq([" fact. ", "#program a().", "#program b(a)."], lines)
    test.eq({'base': [], 'a': [], 'b': [('a', [])]}, programs)


@test
def read_function_args():
    lines, programs = read_programs(""" fact. \n#program a(x). \n #program b(a(42)). """)
    test.eq([" fact. ", "#program a(x).", "#program b(a)."], lines)  # 42 removed
    test.eq({'base': [], 'a': [('x', [])], 'b': [('a', [42])]}, programs)


@test
def check_for_duplicate_test(raises:(Exception, "Duplicate program name: 'test_a'")):
    read_programs(""" #program test_a. \n #program test_a. """)


@test
def simple_program():
    t = parse_and_run_tests("""
        fact.
        #program test_fact(base).
        assert(@all("facts")) :- fact.
        assert(@models(1)).
     """)
    test.eq(('test_fact', {'asserts': {'assert("facts")', 'assert(models(1))'}, 'models': 1}), next(t))


@test
def dependencies():
    t = parse_and_run_tests("""
        base_fact.

        #program one(b).
        one_fact.

        #program test_base(base).
        assert(@all("base_facts")) :- base_fact.
        assert(@models(1)).

        #program test_one(base, one(1)).
        assert(@all("one includes base")) :- base_fact, one_fact.
        assert(@models(1)).
     """)
    test.eq(('test_base', {'asserts': {'assert("base_facts")'       , 'assert(models(1))'}, 'models': 1}), next(t))
    test.eq(('test_one' , {'asserts': {'assert("one includes base")', 'assert(models(1))'}, 'models': 1}), next(t))


@test
def pass_constant_values():
    t = parse_and_run_tests("""
        #program fact_maker(n).
        fact(n).

        #program test_fact_2(fact_maker(2)).
        assert(@all(two)) :- fact(2).
        assert(@models(1)).

        #program test_fact_4(fact_maker(4)).
        assert(@all(four)) :- fact(4).
        assert(@models(1)).
     """)
    test.eq(('test_fact_2', {'asserts': {'assert(two)', 'assert(models(1))'}, 'models': 1}), next(t))
    test.eq(('test_fact_4', {'asserts': {'assert(four)', 'assert(models(1))'}, 'models': 1}), next(t))


@test
def warn_for_disjunctions():
    t = parse_and_run_tests("""
        time(0; 1).
        #program test_base(base).
        assert(@all(time_exists)) :- time(T).
        assert(@models(1)).
     """)
    test.eq(('test_base', {'asserts': {'assert(models(1))', 'assert(time_exists)'}, 'models': 1}), next(t))


@test
def ground_and_solve_basics():
    result = ground_and_solve(["fact."])
    test.eq([clingo.Function('fact')], [s.symbol for s in result.symbolic_atoms.by_signature('fact', 0)])

    result = ground_and_solve(["#program one. fect."], programs=(('one', ()),))
    test.eq([clingo.Function('fect')], [s.symbol for s in result.symbolic_atoms.by_signature('fect', 0)])

    class O:
        @classmethod
        def init_program(self, *a):
            self.a = a
    ground_and_solve(["fict."], observer=O)
    test.eq((True,), O.a)

    class C:
        @classmethod
        def goal(self, *a):
            self.a = a
            return a
    ground_and_solve(['foct(@goal("g")).'], context=C)
    test.eq("(String('g'),)", str(C.a))

    done = [False]
    def on_model(m):
        test.truth(m.contains(clingo.Function('fuct')))
        done[0] = True
    ground_and_solve(['fuct.'], on_model=on_model)
    test.truth(done[0])


@test
def parse_warning_raise_error(stderr):
    with test.raises(SyntaxError, "in ASP code: syntax error, unexpected EOF\nabc\n^"):
        ground_and_solve(["abc"])
    with test.raises(SyntaxError, "in ASP code: atom does not occur in any rule head:  b\na :- b.\n     ^"):
        ground_and_solve(["a :- b."])
    with test.raises(SyntaxError, 'in ASP code: operation undefined:  ("a"/2)\na("a"/2).\n  ^^^^^'):
        ground_and_solve(['a("a"/2).'])

    with test.raises(SyntaxError, """in ASP code: unsafe variables in
a(A) :- b.
^^^^^^^^^^

  a(A):-[#inc_base];b.
    ^
   'A' is unsafe"""):
        ground_and_solve(['a(A) :- b.'])

    with test.raises(SyntaxError, """in ASP code: global variable in tuple of aggregate element:  X
a(1). sum(X) :- X = #sum { X : a(A) }.
                           ^"""):
        ground_and_solve(['a(1). sum(X) :- X = #sum { X : a(A) }.'])


#  TODO:
"""
SyntaxError: in ASP code: unsafe variables in
output(T, R, rijweg_vrij)  :-
    rijweg(R),
    time(T),
    input(T, R, rijweg_ingesteld).   <<<<<<<<<< . niet hier!
    input(T, R, bgz).
    ^^^^^^^^^^^^^^^^^

  input(T,R,bgz):-[#inc_base].
<block>:28:14-15: note: 'R' is unsafe
            ^
           'T' is unsafe
"""

"""
SyntaxError: in ASP code: syntax error, unexpected:, expecting .
                                               ^

Kwam van:
MessageCode.RuntimeError ./interlocking/general/normaal_voorwaarde_h.lp:50:48-49: error: syntax error, unexpected :, expecting .
Er stond: #program test_rijweg_vrij(rijweg_170_182, base):
(: aan het einde, moet . zijn)
"""

# more tests in __init__ to avoid circular imports
