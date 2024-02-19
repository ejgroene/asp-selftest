
#program generate().
{ queen(X, Y) :  X = 1..N,  Y = 1..N } = N  :-  board(N).


#program test_generate(generate).
assert(@models(30)).
board(2).
assert(@all(two_of_four)) :- {queen(X,Y) : X=1..2, Y=1..2} = 2.
board(3).
assert(@all(three_of_nine)) :- {queen(X,Y) : X=1..3, Y=1..3} = 3.


#program test_generate_4(generate).
assert(@models(1820)).
board(4).
assert(@all(four_of_16)) :- {queen(X,Y) : X=1..4, Y=1..4} = 4.



#program constraint(n).
:- queen(X, Y),  queen(X', Y),  X' <> X.
:- queen(X, Y),  queen(X, Y'),  Y' <> Y.  % row
:- queen(X, Y),  queen(X + N, Y + N),  N = 1..M,  board(M).
:- queen(X, Y),  queen(X + N, Y - N),  N = 1..M,  board(M).


#program test_constraints_row(constraint(1)).
queen(1,1).
queen(2,1).
assert(@models(0)).

#program test_constraints_column(constraint(1)).
queen(1,1).
queen(1,2).
assert(@models(0)).

#program test_constraints_diag(constraint(1)).
board(3).
queen(2,2).
queen(3,3).
assert(@models(0)).

#program test_constraints_diag_2(constraint(1)).
board(3).
queen(2,2).
queen(1,3).
assert(@models(0)).

#program test_constraints_pass(constraint(1)).
board(5).
queen(1,1).  queen(2,4).  queen(3,2).  queen(4,5).  queen(5,3).
assert(@all(pass)) :- queen(1,1),  queen(2,4),  queen(3,2),  queen(4,5),  queen(5,3).
assert(@models(1)).
