% Implicit 'base'

% Infer nodes from given edges.
node(A)  :-  edge(A, _).
node(B)  :-  edge(_, B).

% Check that we have at least one edge to work with.
cannot("at least one edge")  :-  not { edge(_, _) } > 0.


#program test_edge_leads_to_nodes(base).

% Test a simple graph of one edge.
edge(x, y).

% The edge above implies nodes x and y, check it.
cannot("node x")  :-  not node(x).
cannot("node y")  :-  not node(y).
cannot("node z")  :-  node(z).  % fails
