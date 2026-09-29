# Bio/positionpaper

In 2024 I sold my company and started on an assignment for the Dutch railway authority ProRail. Their question was: can you automate the design of the logic rules for the rail side signalling (interlocking) systems.

Have no experience with railway interlocking, nor with ASP, I took the assignment. In this paper I describe what I did with ASP and what I would like to see and contribute in the future.


Wishes:

1. namespaces
2. keyword arguments to functions
3. guarded grounding literals in constraints/tests:
   1. cannot("test")  :-  is_a_thing(A),  not some_condition(A, x).
   2. is_a_thing(A) can be false, which is not the intended test.
   3. is_a_thing(A) is only there to ground A, not as a condition.
4. index operator on tuples
5. 
