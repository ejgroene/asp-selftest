# asp-selftest
In-source test runner for Answer Set Programming (ASP) with Clingo.

GOAL
----

Enable first class unit testing in ASP using native ASP code and as much known concepts and as few magic as possible.

IDEA
----

1. Use `#program`'s to identify units and their dependencies. Here we have a unit called `unitA` with a unit test for it called `testunitA`.

    #program unitA.
    
    #program testunitA(unitA).

2. Extend the notion of `#program` a bit by allowing to use functions for constants.  This allows `#program` units with constants being tested. Here is a unit `step` that is tested with constant `a` being substituted with `2`:

    #program step(a).
    
    #program test_step(step(2)).

3. Within a test program, use `assert` with a `@name` to ensure universal truths that must be in every model. We use `@name` to communicate to the runtime that this particular assert must be checked for presence in every model.

    #program part.
    { fix(A) : A=1..N } = 1 :- n(N).
    
    #program testpart(part).
    n(10).
    assert(@name(select_one)) :- { fix(X) : X=1..10 } = 1.

4. To enable testing constraints and to guard tests for empty model sets, we use `@models` to check for the expected number of models. In the example above, we would add:

    assert(@models(10)).

TESTING
-------

Tests are run using the testrunner:

    $ python runtests.py example.lp
    teststep,  2 asserts,  10 models.  OK

To use the program without the tests use:

    $ python runtests.py --main example.lp <more files>


