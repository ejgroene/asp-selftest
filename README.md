# asp-selftest
In-source STTCPW test runner for Answer Set Programming (ASP) with Clingo.

It is rough and unpolished, but it works.

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

3. Within a test program, use `assert` with `@all` to ensure universal truths that must be in every model. We use `@all` to communicate to the runtime that this particular assert must be checked for presence in every model. Its argument is just a name for identification.

       #program part.
       { fix(A) : A=1..N } = 1 :- n(N).
       
       #program testpart(part).
       n(10).
       assert(@all(select_one)) :- { fix(X) : X=1..10 } = 1.

4. To enable testing constraints and to guard tests for empty model sets, we use `@models` to check for the expected number of models. In the example above, we would add:

       assert(@models(10)).

5. An interesting use case came up while testing uniqueness of terms. Suppose we want to guard against defining and input twice based on the fact that the first parameter of the function `input` is actually an unique identifier. We have to include this identifier in the assert, since we want it asserted for every possible identifier. So the assert becomes: `assert@all(input_is(Uniq)))`, with `Uniq`  being the identifier:

       #program define_inputs().
       input(input_a, 1, position(4), "Input A").       % full definition
       input(input_b, 2, position(3), "Input B").       % full definition
       input(Id)  :-  input(Id, _, _, _).               % shortcut for easier testing

       #program test_inputs(define_inputs).
       assert(@models(1)).
       assert(@all(input_is(Uniq)))  :-  input(Uniq),  { input(Uniq, _, _, _) } = 1.

   Note that if we would just write `assert(@all(input_is_unique))`, the test would succeed as long as if there is al least one input not defined twice, leaving all others untested. It turned out that the software could already do this. Only the name of the argument in Python changed from `name` to `term`.

TESTING
-------

Tests are run using the testrunner:

    $ python asp-tests example.lp
    teststep,  2 asserts,  10 models.  OK

To use the program without the tests: Not Yet Implemented. But you can use the `base` program anywhere of course, since all `#program`s are ignored by default.
