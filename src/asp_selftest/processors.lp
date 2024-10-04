processor("PrintGroundSymbols").
processor("Reify").

define(179, stuur, "A", "N/A").
output(T, Device, Function) :- reify(Function, T, Device),  define(179, Function, _, _).

reify(Function, T, Device)  :-  define(Device, Function, _, _),  stuur(T, Device).

%stuur(0, 179) :-  blah.

#external input(0, 177, stuur).
reify(Function, T, Device) :- input(T, Device, Function).

