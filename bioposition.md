# Bio/positionpaper

In 2024, after 22 years, I sold my company and began an assignment for ProRail, the Dutch railway infrastructure manager. The central question was whether the logic rules governing railway interlocking systems could be designed automatically.

Although I had no prior experience with railway interlocking or ASP, I took on the assignment. It offered an opportunity to investigate a challenging problem in an unfamiliar domain and to explore approaches that might extend what is currently considered feasible.

This paper describes how I applied ASP to the problem, how the resulting work is used today, and the directions I hope to pursue and contribute to in the future.

Wishes:

1. namespaces
2. keyword arguments to functions
3. guarded grounding literals in constraints/tests:
   1. cannot("test")  :-  is_a_thing(A),  not some_condition(A, x).
   2. is_a_thing(A) can be false, which is not the intended test.
   3. is_a_thing(A) is only there to ground A, not as a condition.
4. index operator on tuples
5. 
