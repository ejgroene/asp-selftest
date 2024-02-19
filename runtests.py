from clingo import Number, String, Function, Symbol, Control
import sys, re

"""
Supports running test in Answer Set Programming (ASP).

Units to be tested must be designated with #program, for example:

#program generate().
{ queen(X, Y) :  X = 1..N,  Y = 1..N } = N  :-  board(N).


Unit tests are also designated with #program. The name must
start with 'test_' and the constants indicate depencencies,
for example:

#program test_generate(generate).
board(2).
test(@name(two_of_four)) :- {queen(X,Y) : X=1..2, Y=1..2} = 2.


This will ground and solve test_generate with generate. The
only requirement is that the constants refer to #program's. At runtime
the constants (generate) have the fixed value 1.


Assertions are created by creating and naming an atom called test:

test(@name=<name>) :- <a body>

@name registers the term test(<name>) and checks afterwards if it
appears in all answer sets. The body is any ASP code you want. The
name must be unique.

When executed, runtests.py finds all #program test_* and grounds and
solves them one by one, each time checking if the test(...) terms
are part of all answers. On first failure, It prints that model and 
the failed term.
"""

program_file = sys.argv[1]
program = open(program_file).read()

programs = {}

# read all the #program parts and their dependencies
for line in program.splitlines():
    if line.startswith('#program'):
        signature = line.split('#program')[1].strip()
        name, deps = signature[:-2].split('(')
        dep_names = [d for d in deps.split(',') if d]
        if name in programs:
            raise Exception("Duplicate test name: " + name)
        programs[name] = dep_names


class Tester:

    def __init__(self):
        self._asserts = set()
        self._models_ist = 0
        self._models_soll = -1

    def name(self, name):
        assrt = Function("assert", [name])
        if assrt in self._asserts:
            """ does not work because rules are expanded """
            #raise Exception("Duplicate assertion name: " + str(name))
        self._asserts.add(assrt)
        return name

    def models(self, n):
        """ asserts the total number of models found """
        self._models_soll = n.number
        models_term = Function("models", [n])
        assrt = Function("assert", [models_term])
        self._asserts.add(assrt)
        return models_term

    def on_model(self, model):
        self._models_ist += 1
        #print("#%s" % self.n, end=': ')
        for assrt in self._asserts:
            if not model.contains(assrt):
                print(model)
                print("FAILED:", assrt)
                raise SystemExit
        return model

    def report(self):
        assert self._models_ist == self._models_soll, self._models_ist
        print(" %s asserts,  %s models.  OK" % (len(self._asserts), self._models_ist))


n = 0
for name, deps in programs.items():
    tester = Tester()
    if name.startswith('test'):
        n += 1
        print(name, end=', ', flush=True)
        control = Control(['0'])
        control.add(program)
        testprogram = (name, [Number(1) for _ in deps])
        depprograms = []
        for depname in deps:
            depdeps = programs[depname]
            depprograms.append((depname, [Number(1) for _ in depdeps]))
        control.ground(
                [testprogram] + depprograms,
                context = tester
        )
        control.solve(on_model=tester.on_model)
        tester.report()
