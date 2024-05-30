% This program demonstrates duplicate asserts and how to solve it.

#program define_ids.
def_id("Room 1", 4, 5).
def_id("Room 2", 3, 2).
def_id("Room 3", 3, 2).
def_id("Room 3", 5, 2).  % reused id, our test must detect this


#program test_define_ids_wrong_way(define_ids).
% This test does not detect the duplicate Id "Room 3".
% The system gives a warning though: WARNING: duplicate assert: assert(id_uniq).
%           disjunction
%               V
assert(@all(id_uniq))  :-  def_id(Id, _, _),  { def_id(Id, _, _) } = 1.
assert(@models(1)).


#program test_define_ids_right_way(define_ids).
% This test detects the duplicate Id and fails.
% It generates unique asserts for every Id.
%                 unique
%                    V
assert(@all(id_uniq(Id)))  :-  def_id(Id, _, _),  { def_id(Id, _, _) } = 1.
assert(@models(1)).
