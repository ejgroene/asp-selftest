# asp-selftest
In-source test runner for Answer Set Programming (ASP) with Clingo.

It provides:

    * `asp-tests`: a standalone (Python) tool to run tests in a logic program.
    * `bin/runasptests.sh`: Bash script to find all .lp files and run their tests.

Both tools stop at first failure.


GOAL
----

Enable first class unit testing in ASP using native ASP code and as much known concepts and as few magic as possible.

IDEA
----

1. Use `#program`'s to identify units and their dependencies. Here we have a unit called `unitA` with a unit test for it called `testunitA`.

       #program unit_A.
    
       #program test_unit_A(unit_A).

   The implicit program `base` (see Clingo Guide) must be referenced explicitly if needed.


2. Extend the notion of `#program` by allowing the use of functions instead of only constants.  This allows `#program` units with constants being tested. Here is a unit `step` that is tested with constant `a` being substituted with `2`:

       #program step(a).
    
       #program test_step(step(2)).

   Note that using this feature makes the program incompatible with Clingo. The test runner has an option to transform a extended program back to compatible Clingo without running the tests.


3. Within a test program, use `assert` with `@all` to ensure universal truths that must be in every model. We use `@all` to communicate to the runtime that this particular assert must be checked for presence in every model. Its argument is just a name for identification.

        #program step(n).
        fact(n).

        #program test_step(step(3)).
        assert(@all("step fact"))  :-  fact(3).

   Note that `"step fact"` is just a way of distinquishing the assert. It can be an atom, a string, a number or anything else. Pay attention to the uniqueness in case of variables in the body. Take note of point 5 below.


4. To enable testing constraints and to guard tests for empty model sets, we use `@models` to check for the expected number of models. In the example above, we would add:

        assert(@models(1)).


5. Care must be taken if variables in the body lead to expansion and conjunctions. See `duplicate_assert.lp`. The system gives a warning for:

        assert(@all(id_uniq))  :-  def_id(Id, _, _),  { def_id(Id, _, _) } = 1.

    Instead you have to write:

        assert(@all(id_uniq(Id)))  :-  def_id(Id, _, _),  { def_id(Id, _, _) } = 1.


TESTING
-------

Tests are run using the testrunner:

    $ python asp-tests example.lp
    teststep,  2 asserts,  10 models.  OK

To use the program without the tests: Not Yet Implemented. But you can use the `base` program anywhere of course, since all `#program`s are ignored by default.
