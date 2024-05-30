fact(core).

#program step(n).
fact(n).

#program test_step(base, step(3)).
assert(@all("core fact"))  :-  fact(core).
assert(@all("step fact"))  :-  fact(3).
assert(@models(1)).

