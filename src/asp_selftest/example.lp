#program step(n).
{ fix(A) : A=1..n } = 1.

#program teststep(step(10)).
assert(@all(select_one(Y))) :- Y=1..10,  { fix(X) : X=1..10 } = 1.  % not sure if this is a good test; don't think so; something got lost during refactoring
assert(@models(10)).


#program define_inputs().
input(input_a, 1, position(4), "Input A").       % full definition
input(input_b, 2, position(3), "Input B").       % full definition
input(Id)  :-  input(Id, _, _, _).               % shortcut for easier testing


#program test_inputs(define_inputs).
assert(@models(1)).
assert(@all(input_is(Uniq)))  :-  input(Uniq),  { input(Uniq, _, _, _) } = 1.
