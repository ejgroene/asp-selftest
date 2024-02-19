#program step(n).
{ fix(A) : A=1..n } = 1.

#program teststep(step(10)).
assert(@all(select_one)) :- { fix(X) : X=1..10 } = 1.
assert(@models(10)).
