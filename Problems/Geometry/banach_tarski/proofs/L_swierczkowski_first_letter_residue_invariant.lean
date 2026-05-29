-- Reduce the Swierczkowski freeness invariant to pure-ℤ residue combinatorics
-- plus a matrix bridge. `step` is the concrete integer recursion (one branch per
-- generator letter), and `hstep` records its four defining equations.
--   • `residue_invariant_foldr_list` carries the inductive mod-3 residue invariant
--     on the reduced word list — no matrices, no √2, just integers (the real
--     induction, where ∃p q r,¬3∣q had to be strengthened to the head?-keyed
--     residue disjunction to become inductive).
--   • `matrix_prod_realizes_triple` transports the resulting integer triple back
--     through the generator matrices acting on ![0,1,0] (cites the proved
--     `matrix_prod_mulvec_realizes_foldr` + `rotation_generators_integer_recursion`).
-- The head?-residue disjunction is identical in parent and sub-goal A, so it
-- threads through unchanged.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11396

namespace Problems.Geometry.banach_tarski

def swierczkowski_first_letter_residue_invariant := @Problems.Geometry.banach_tarski.s11396

end Problems.Geometry.banach_tarski
