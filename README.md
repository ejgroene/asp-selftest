# asp-selftest

Starting with in-source testing in mind, `asp-selftest` has evolved into:

 1. **In-source** test runner for _Answer Set Programming_ (`ASP`) with [Clingo](https://potassco.org).
 2. Rich `SyntaxError`s with `ASP` source, based on Clingo's log messages.
 3. Minimalistic **plugins** based on `ASP` predicates used as directives.
    (plugins: reification, clingo_main, dynamic plugins, sequencing, testrunner, mimic default clingo)

## In-source Testing

It allows one to write **constraints** in ASP that will automatically be checked on loading. Consider `logic.lp` which contains:

    node(A)  :-  edge(A, _).
    node(B)  :-  edge(_, B).
    
    cannot("at least one edge")  :-  not { edge(_, _) } > 0.
    
    #program test_edge_leads_to_nodes(base).
    edge(x, y).
    cannot("node x")  :-  not node(x).
    cannot("node y")  :-  not node(y).
    cannot("node z")  :-  not node(z).  % fails

Using `cannot` we capture the results from constraints that _cannot be true_. This leads to the following output:

    $ clingo+ logic.lp --run-tests
    ...
    AssertionError: cannot("at least one edge")
    File test.lp, line 1, in base().
    Model:
    <empty>

If we fix it (remove it), we get the next failure:

    $ clingo+ logic.lp --run-tests
    ...
    AssertionError: cannot("node z")
    File test.lp, line 5, in test_edge_leads_to_nodes(base).
    Model:
    edge(x,y)  node(x)    node(y)


## SyntaxError

If we make a mistake, it tells us in a sensible way:

    $ clingo+ logic.lp
    ...
    Traceback (most recent call last):
      ...
      File "logic.lp", line 2
        1 node(A)  :-  edge(A, _).
        2 node(B)  :-  edge(_, A).
               ^ 'B' is unsafe
          ^^^^^^^^^^^^^^^^^^^^^^^^ unsafe variables in:  node(B):-[#inc_base];edge(#Anon0,A).


## Status

This tools is still a **work in progress**. I use it for a project to providing **formal specifications** for **railway interlocking**. It consist of 35 files, 100+ tests and 600+ `cannot`s.


`asp-selftest` has been presented at [Declarative Amsterdam in November 2024](https://declarative.amsterdam/program-2024).


## Changes

From version `v0.0.30` upwards, `@all`, `@any`, `@model` and the special treatment of predicate `assert` are **removed**.
From this version on, only `cannot` is supported.

Tests from `#include` files are run in their own context, making it easier to add `cannot` to `base`-parts.

It is tenfold **faster**. It runs all my 100+ tests in less than 2 seconds.

Also, `asp-test` is removed. Only `clingo+` remains. The latter is a drop-in replacement for `clingo` with the added ability to activate `plugins`, of which these are default:

 1. `TesterHook` - runs in-source unit tests.
 2. `SyntaxErrorHandler` - provides nice in-source error messages, a la Python

You can write you own plugins. I have one for `reifying` rules from theory atoms, for example.

## Why In-Source?

With `in-source` testing, source and tests stay together in the same file. This enables automatic collection and running and avoid maintaining a test tree, and it eases refactoring greatly.

# Installing and running

## Installing

    pip install asp-selftest

Run it using:

    $ clingo+ <file.lp> --run-tests

There is one additional option to silence the in-source Python tests:

    $ clingo+ --silent --run-tests


# A bit of documentation

1. Use `#program`'s to specify tests and their dependencies. Here we have a unit called `unit_A` with a unit test for it called `test_unit_A`. Test must start with `test_`. Formal arguments are treated as dependencies.

       #program unit_A.
    
       #program test_unit_A(base, unit_A).

    The implicit program `base` (see Clingo Guide) must be referenced explicitly if needed.

    The actual arguments to `test_unit_a` will be a generic placeholder and have no meaning inside `test_unit_A`.

2. Within a test program, use `cannot` much like ASP constraints, only with a head. Its arguments are just for identification in the reporting.

        #program step.
        fact.

        #program test_step(step).
        cannot("step fact")  :-  not fact(3).

   Note that `"step fact"` is just a way of distinquishing the constraint. It can be an atom, a string, a number or anything else.

3. Note that `cannot` is much like an _constraint_ in `ASP`.  To assert `somefact` is true, we must use `not`:

        somefact.
        cannot("somefact must be true")  :-  not somefact.

    It is helpful to read `cannot` as _it cannot be the case that..._.  Alternatively, one can use `constraint` as an alias for `cannot`.  Just your preference.

