# asp-selftest

In-source unit testing for **Answer Set Programming** (ASP).


## In-source Unit Testing

Consider `nodes.lp` which contains a test `test_edge_leads_to_nodes`:

```prolog
% Implicit 'base'

% Infer nodes from given edges.
node(A)  :-  edge(A, _).
node(B)  :-  edge(_, B).

% Check that we have at least one edge to work with.
cannot("at least one edge")  :-  not { edge(_, _) } > 0.


#program test_edge_leads_to_nodes(base).

% Test a simple graph of one edge.
edge(x, y).

% The edge above implies nodes x and y, check it.
cannot("node x")  :-  not node(x).
cannot("node y")  :-  not node(y).
cannot("node z")  :-  not node(z).  % fails
````

The test contains three `cannot` predicates. Think of these as **inverted asserts** (more on this later).

It also contains one `cannot` in the (implicit) `base`-part of the program. If we run it, this one fails first:

```shell
$ clingo+ logic.lp --run-asp-tests
...
Testing logic.lp
  base()
...
AssertionError: cannot("at least one edge")
File test.lp, line 1, in base().
Model:
<empty>
```

Oops, we forgot to add edges, so let's add `edges.lp`:

```shell
$ clingo+ logic.lp edges.lp --run-asp-tests
...
Testing logic.lp
  base()
  test_edge_leads_to_nodes(base)
...
AssertionError: cannot("node z")
File logic.lp, line 6, in test_edge_leads_to_nodes(base). Model follows.
edge(x,y)
node(x)
node(y)
```

Now `base` is OK, but the test fails. We can fix that by removing `not` from the lastt `cannot`:

```prolog
cannot("node z")  :-  node(z).
````

As custom with in-source unit testing, it fails fast: it quits on the first failure.


## Test Dependencies

We use `#program`'s to specify tests and their dependencies. Below we have a unit called `unit_A` with a unit test called `test_unit_A`. (Test must start with `test_`.) *Formal* arguments are treated as dependencies:

```prolog
#program unit_A.
    
#program test_unit_A(base, unit_A).
```

The implicit program `base`[^guide] must be referenced explicitly if needed.

The *actual* arguments to `test_unit_A` are undefined.


## Scoping

Tests in each file run in the context of only that file. If file A includes file B, then the tests in B will run with only the logic in B loaded. The tests in A run with the logic from A and B loaded.


## SyntaxError

If we make a mistake, it tells us in a sensible way:

```prolog
$ clingo+ logic.lp
...
Traceback (most recent call last):
  ...
  File "logic.lp", line 2
    1 node(A)  :-  edge(A, _).
    2 node(B)  :-  edge(_, A).
           ^ 'B' is unsafe
      ^^^^^^^^^^^^^^^^^^^^^^^^ unsafe variables in:  node(B):-[#inc_base];edge(#Anon0,A).
```

## More on `cannot`

The use of `cannot` instead of a positive `assert` might seem counter intuitive, but it is not. It would require you to learn a non-trivial arsenal of idioms in order to avoid asserts to be optimized away. Instead we use constraints[^guide].

[^guide]: Potassco User Guide $3.1.2

Constraints have no head and must alway be false. If yet it becomes true, the ASP runtime considers the model invalid. 

We use `cannot` as the head for a constraint. Now when it becomes true, the runtime will ignore it, and it will just end up in the model.

It is helpful to read `cannot` as _it cannot be the case that..._.  

This can be seen when running the example above without `--run-asp-tests`:

```shell
$ clingo+ logic.lp
clingo+ version 5.8.0
Reading from logic.lp
Solving...
Answer: 1 (Time: 0.001s)
cannot("at least one edge")
SATISFIABLE
```

We just raise errors for `cannot`s in a model. 

Now, if you can write constraints, you can write `cannot`s.


## Status

This tools is still a **work in progress**. I use it for a project to providing **formal specifications** for **railway interlocking**. It consist of 35 files, 100+ tests and 600+ `cannot`s.


`asp-selftest` has been presented at [Declarative Amsterdam in November 2024](https://declarative.amsterdam/program-2024).


# Installing and running

## Installing

    pip install asp-selftest

Run it using:

    $ clingo+ <file.lp> --run-asp-tests

There is one additional option to run the in-source Python tests:

    $ clingo+ --run-python-tests
