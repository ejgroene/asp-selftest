#!/usr/bin/env python3
import inspect
import clingo
import sys
import ast
import selftest
test = selftest.get_tester(__name__)


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


@test
def parse_some_signatures():
    test.eq(('one', [('two', []), ('three', [])]), parse_signature("one(two, three)"))
    test.eq(('one', [2, 3]), parse_signature("one(2, 3)"))
    test.eq(('one', [('two', [2, ('aap', [])]), ('three', [42])]), parse_signature("one(two(2, aap), three(42))"))


""" Selftest uses the context for supplying the functions @all and @models to the ASP program. 
    As a result the ASP program own Python functions are ignored. To reenable these, they must
    be registered using register(func).
"""
current_tester = None

def register(func):
    assert inspect.isfunction(func), f"{func} must be a function"
    global current_tester
    if current_tester:    # we might not run, actually...
        current_tester.add_function(func)


class Tester:

    def __init__(self):
        self._asserts = set()
        self._models_ist = 0
        self._models_soll = -1
        self._funcs = {}

    def all(self, *args):
        """ ASP API: add a named assert to be checked for each model """
        self._asserts.add(clingo.Function("assert", args))
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
        return self._funcs[name]


def do_tests(asp_code):
    lines = asp_code.splitlines()
    # read all the #program parts and register their dependencies
    programs = {}
    for i, line in enumerate(lines):
        if line.strip().startswith('#program'):
            name, deps = parse_signature(line.split('#program')[1].strip()[:-1])
            if name in programs:
                raise Exception("Duplicate test name: " + name)
            programs[name] = deps
            # rewrite into valid ASP (turn functions into plain terms)
            lines[i] = f"#program {name}({','.join(dep[0] for dep in deps)})."

    for name, deps in programs.items():
        if name.startswith('test'):
            global current_tester
            tester = current_tester = Tester()
            control = clingo.Control(['0'])
            control.add('\n'.join(lines))

            programs = [(name, [clingo.Number(1) for _ in deps])] + \
                       [(depname, [clingo.parse_term(str(a)) for a in depargs]) for depname, depargs in deps]
            control.ground(programs, context = tester)
            control.solve(on_model = tester.on_model)
            yield name, tester.report()



def runasptests():
    for program_file in sys.argv[1:]:
        print(f"Reading {program_file}.", flush=True)
        lines = open(program_file).read()
        for name, result in do_tests(lines):
            asserts = result['asserts']
            models = result['models']
            print(f"ASPUNIT: {name}: ", end='', flush=True)
            print(f" {len(asserts)} asserts,  {models} model{'s' if models>1 else ''}")
        #sys.tracebacklimit = 0


if __name__ == '__main__':
    runasptests()


@test
def simple_program():
    t = do_tests("""
        fact.
        #program test_fact(base).
        assert(@all("facts")) :- fact.
        assert(@models(1)).
     """)
    test.eq(('test_fact', {'asserts': {'assert("facts")', 'assert(models(1))'}, 'models': 1}), next(t))


