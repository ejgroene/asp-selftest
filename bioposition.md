# Bio/positionpaper

E.J. Groeneveld, ejgroene@ieee.org

## Occupation

In 2024, after 22 years, I sold my company and began an assignment for `ProRail`, the *Dutch railway infrastructure manager*. The central question was whether the logic rules governing railway interlocking systems could be designed automatically.

Although I had no prior experience with railway interlocking or `ASP`, I took on the assignment. It offered an opportunity to investigate a challenging problem in an unfamiliar domain and to explore approaches that might extend what is currently considered feasible.

This paper describes how I applied `ASP` to the problem, how the resulting work is used today, and the directions I hope to pursue and contribute to in the future.

## SIL-4 context

Interlocking developments and deployments are subject to stringent SIL-4 safety standards which have greatly influenced the solution. The effort needed to ensure that the solution is actually used and fruitful is at least equal to the intellectual effort needed to devise and implement this solution. 

## Foundational Design Principle

The most prominent design influence was the choice to create an (almost) ASP-only solution, in which railway engineers are always in charge and have the final say. At no point were engineers interviewed and their knowledge coded into ASP. The solution is a tool to let them work faster, create more reliable en predictable results and have automatic verification at each stage. Since the whole system is steadily becoming specified in ASP, formal verification of correctness is the next step to take.

## Use of ASP

- Vital Logic
- concept mapping
- cross compiler
- unit tests
- integration tests

## ASP Maturity

Wishes:

1. namespaces
2. keyword arguments to functions
3. guarded grounding literals in constraints/tests:
   1. cannot("test")  :-  is_a_thing(A),  not some_condition(A, x).
   2. is_a_thing(A) can be false, which is not the intended test.
   3. is_a_thing(A) is only there to ground A, not as a condition.
4. index operator on tuples
5. #const etc scoped to #program
6. #include in ast
7. previous two points: in large programs, one part may include a file that is also include elsewhere. For decomposing large programs, it is a necessity that each part includes its own stuff, for reasons such as that is separately testable for example. Duplicate includes can be ignored, and that works, but the included file defines a #const, that will cause an error the second time it is included. This can not be avoided. 
8. plash or unpack operation, like Python *iter.
9. dot operator (for namespaces and objects)
