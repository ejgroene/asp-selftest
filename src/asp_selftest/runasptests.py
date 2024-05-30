
""" Functions to runs all tests in an ASP program. """

import inspect
import clingo
import sys
import ast


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


current_tester = None


def register(func):
    """ Selftest uses the context for supplying the functions @all and @models to the ASP program. 
        As a result the ASP program own Python functions are ignored. To reenable these, they must
        be registered using register(func).
    """
    assert inspect.isfunction(func), f"{func!r} must be a function"
    global current_tester
    if current_tester:
        current_tester.add_function(func)


class Tester:

    def __init__(self):
        self._asserts = set()
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


    def models(self, n):
        """ ASP API: add assert for the total number of models """
        self._models_soll = n.number
        return self.all(clingo.Function("models", [n]))


    def on_model(self, model):
        """ Callback when model is found; count model and check all asserts. """
        self._models_ist += 1
        failures = [a for a in self._asserts if not model.contains(a)]
        assert not failures, f"FAILED: {', '.join(map(str, failures))}\nMODEL: {model}"
        return model


    def report(self):
        """ When done, check assert(@models(n)) explicitly, then report. """
        assert self._models_ist == self._models_soll, f"Expected {self._models_soll} models, found {self._models_ist}."
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


def run_tests(lines, programs):
    for prog_name, dependencies in programs.items():
        if prog_name.startswith('test'):
            global current_tester
            tester = current_tester = Tester()
            control = clingo.Control(['0'])
            control.add('\n'.join(lines))

            def prog_with_dependencies(name, dependencies):
                yield name, [clingo.Number(42) for _ in dependencies]
                for dep, args in dependencies:
                    formal_args = programs.get(dep, [])
                    formal_names = list(a[0] for a in formal_args)
                    if len(args) != len(formal_names):
                        raise Exception(f"Argument mismatch in {prog_name!r} for dependency {dep!r}. Required: {formal_names}, given: {args}.")
                    yield dep, [clingo.Number(a) for a in args]

            to_ground = list(prog_with_dependencies(prog_name, dependencies))
            control.register_observer(tester)
            control.ground(to_ground, context = tester)
            control.solve(on_model = tester.on_model)
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
def register_asp_function():
    global current_tester
    def f(a):
        pass
    test.eq(None, current_tester)
    register(f)
    test.eq(None, current_tester)
    fs = []
    class X:
        def add_function(self, f):
            fs.append(f)
    try:
        current_tester = X()
        register(f)
        test.eq(f, fs[0])
    finally:
        current_tester = None


@test
def register_asp_function_is_function(raises:(AssertionError, "'aap' must be a function")):
    register("aap")


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


# more tests in __init__ to avoid circular imports
