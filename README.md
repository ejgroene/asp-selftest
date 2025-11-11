# asp-selftest

A unit testing framework for **Answer Set Programming** (ASP) that enables in-source test definitions and execution.

## Overview

`asp-selftest` extends the Clingo ASP solver with integrated testing capabilities, allowing developers to write and execute unit tests directly within their logic programs. Tests are defined using standard ASP syntax and executed in isolated contexts to ensure reliability and maintainability.

## Quick Start

### Installation

```bash
pip install asp-selftest
```

### Basic Usage

```bash
clingo+ <file.lp> --run-asp-tests
```

## Core Concepts

### In-Source Unit Testing

Tests are embedded directly in ASP source files using `#program` directives. Consider the following example from `nodes.lp`:

```prolog
% Implicit 'base' program

% Infer nodes from given edges.
node(A)  :-  edge(A, _).
node(B)  :-  edge(_, B).

% Verify that at least one edge exists.
cannot("at least one edge")  :-  not { edge(_, _) } > 0.


#program test_edge_leads_to_nodes(base).

% Test data: a simple graph with one edge.
edge(x, y).

% Assertions: verify expected node inference.
cannot("node x")  :-  not node(x).
cannot("node y")  :-  not node(y).
cannot("node z")  :-  not node(z).  % This assertion will fail
```

### The `cannot` Predicate

The framework uses `cannot` predicates as inverted assertions. This design leverages ASP's constraint mechanism to avoid optimization issues that would affect traditional positive assertions.

**Execution Example:**

```shell
$ clingo+ nodes.lp --run-asp-tests
...
Reading from nodes.lp
Testing nodes.lp
  test_edge_leads_to_nodes(base)
...
AssertionError: cannot("node z")
File nodes.lp, line 11, in test_edge_leads_to_nodes(base). Model follows.
edge(x,y)
node(x)
node(y)
```

The test fails because `node(z)` does not exist in the model. To correct this assertion:

```prolog
cannot("node z")  :-  node(z).
```

### Validating Base Programs

After unit tests pass, the framework validates the base program. If prerequisites are missing, appropriate errors are reported:

```shell
$ clingo+ nodes.lp --run-asp-tests
...
AssertionError: cannot("at least one edge")
File nodes.lp, line ?, in base. Model follows.
<empty model>
```

Adding the required data file resolves the issue:

```shell
$ clingo+ nodes.lp edges.lp --run-asp-tests
...
Testing nodes.lp
  test_edge_leads_to_nodes(base)
Testing edges.lp
Testing base
  base
Solving...
Answer: 1 (Time: 0.003s)
edge(a,b) node(b) node(a)
SATISFIABLE
```



## Test Dependencies

Tests and their dependencies are specified using `#program` directives. Test names must begin with the `test_` prefix. Formal parameters declare dependencies on other program units:

```prolog
#program unit_A.
    
#program test_unit_A(base, unit_A).
```

The implicit `base` program[^guide] must be explicitly referenced when required as a dependency. Actual arguments to test programs are not defined.

[^guide]: Potassco User Guide §3.1.2

## Test Scoping

The framework enforces strict test isolation:

- Tests in each file execute within the context of that file only
- When file A includes file B:
  - Tests in B execute with only B's logic loaded
  - Tests in A execute with both A's and B's logic loaded

This scoping ensures that tests remain independent and do not interfere with each other.

## Error Reporting

The framework provides clear, actionable error messages for syntax and semantic errors:

```shell
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

## Understanding `cannot` Predicates

The framework uses `cannot` predicates rather than positive assertions for technical reasons related to ASP's optimization behavior. Traditional positive assertions can be optimized away by the solver, requiring complex idioms to prevent this. The `cannot` approach leverages ASP's constraint mechanism[^guide] for more reliable testing.

### Technical Background

In ASP, constraints are headless rules that must always evaluate to false. When a constraint becomes true, the runtime considers the model invalid. The natural reading of a constraint is: *"it cannot be the case that..."*

By using `cannot` as a predicate head rather than a constraint, the framework allows these predicates to appear in models when they become true. The test runner then inspects the model and raises errors for any `cannot` predicates present.

**Example without test execution:**

```shell
$ clingo+ logic.lp
clingo+ version 5.8.0
Reading from logic.lp
Solving...
Answer: 1 (Time: 0.001s)
cannot("at least one edge")
SATISFIABLE
```

The `cannot` predicate appears in the model, which the test runner would flag as a failure. This approach provides a straightforward testing mechanism: if you can write ASP constraints, you can write `cannot` assertions.

## Architecture

### Plugin System

`asp-selftest` is built on a flexible plugin architecture that enables modular extension and customization of the testing framework. The plugin system uses a functional composition pattern where each plugin wraps the next in a processing chain, allowing for clean separation of concerns and easy extensibility.

The core plugin chain includes:

- **clingo_main_plugin**: Provides CLI integration and argument handling
- **stdin_to_tempfile_plugin**: Manages input from stdin by converting it to temporary files
- **clingo_syntaxerror_plugin**: Enhances error messages with rich formatting and context
- **clingo_sequencer_plugin**: Orchestrates the standard Clingo workflow (Load → Ground → Solve)
- **testrunner_plugin**: Discovers and executes tests, enforcing isolation and dependency management
- **clingo_reify_plugin**: Provides ASP reification support for advanced meta-programming
- **clingo_defaults_plugin**: Configures default behaviors and settings

Each plugin receives the next plugin in the chain as its first argument and can intercept, modify, or enhance the processing pipeline. This architecture allows developers to extend the framework with custom plugins for specialized testing scenarios or integration with other tools.

## Project Status

`asp-selftest` is actively maintained and used in a production environment. The framework has been successfully deployed for formal specification of railway interlocking systems, comprising 35 files, over 100 tests, and more than 600 assertions.

The project was presented at [Declarative Amsterdam in November 2024](https://declarative.amsterdam/program-2024).

## Installation and Usage

### Installation

```bash
pip install asp-selftest
```

### Running ASP Tests

```bash
clingo+ <file.lp> --run-asp-tests
```

### Running Python Tests

The framework includes support for in-source Python tests:

```bash
clingo+ --run-python-tests
```

## Requirements

- Python 3.13 or higher
- Clingo 5.8.0 or higher

## License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.

## Contributing

Contributions are welcome. Please ensure that all tests pass before submitting pull requests.

## Repository

This project has been migrated from GitHub to Codeberg.
