#script (python)
processor(PrintGroundSymbols())
processor(Reify())
#end.

% ondersteuning nodig voor:
% verzoek(T, D)  :-  input(T, D, F).
% output(T, D)  :-  stuur(T, D).
% met dit:
% reify(verzoek, T, Device)  :-  input(T, Device, verzoek),  def_input(Device, verzoek, Bool).
% output(T, Device, stuur)   :-  reify(stuur, T, Device),  def_output(Device, stuur, Bool).
%

reify(F, Y) :- a(X),  b(F, X),  Y = X+1,  Y < 10.


b(a, 0).

#program test_aap.
ensure(aap).
