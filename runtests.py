import clingo
import sys
import ast

def parse(o):
    return o.value if isinstance(o, ast.Constant) else \
           (o.id, []) if isinstance(o, ast.Name) else \
           (o.func.id, [parse(a) for a in o.args])

def parse_signature(s):
    # parse extended #program syntax using Python's parser
    return parse(ast.parse(s).body[0].value)

p = parse_signature("one(two, three)")
assert p == ('one', [('two', []), ('three', [])]), p
p = parse_signature("one(2, 3)")
assert p == ('one', [2, 3]), p
p = parse_signature("one(two(2, aap), three(42))")
assert p == ('one', [('two', [2, ('aap', [])]), ('three', [42])]), p

program_file = sys.argv[1]

# read all the #program parts and register their dependencies
lines = open(program_file).readlines()
programs = {}
for i, line in enumerate(lines):
    if line.startswith('#program'):
        name, deps = parse_signature(line.split('#program')[1].strip()[:-1])
        if name in programs:
            raise Exception("Duplicate test name: " + name)
        programs[name] = deps
        # rewrite into valid ASP (turn functions into plain terms)
        lines[i] = f"#program {name}({','.join(dep[0] for dep in deps)})."


class Tester:

    def __init__(self):
        self._asserts = set()
        self._models_ist = 0
        self._models_soll = -1

    def all(self, name):
        """ ASP API: add a named assert to be checked for each model """
        self._asserts.add(clingo.Function("assert", [name]))
        return name

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
        print(f" {len(self._asserts)} asserts,  {self._models_ist} models.  OK")


for name, deps in programs.items():
    sys.tracebacklimit = 0
    control = clingo.Control(['0'])
    control.add('\n'.join(lines))
    if name.startswith('test'):
        print(name, end=', ', flush=True)
        tester = Tester()
        control.ground(
            [(name, [clingo.Number(1) for _ in deps])] +
            [(depname, [clingo.parse_term(str(a)) for a in depargs]) for depname, depargs in deps],
            context = tester
        )
        control.solve(on_model=tester.on_model)
        tester.report()
