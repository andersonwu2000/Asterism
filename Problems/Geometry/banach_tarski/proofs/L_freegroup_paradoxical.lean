-- Direct assembly of the F₂ paradoxical-decomposition data from two sub-goals.
-- Conjunct 1 (PairwiseDisjoint over the 4 head-letters): each pair reduces to
--   `starts_disjoint` (distinct head? ⇒ disjoint word-sets).
-- Conjuncts 2,3 (translate-covers): `translate_starts_eq_compl i/j` rewrites
--   `of x • W_{x,false}` to `(W_{x,true})ᶜ`, then `Set.union_compl_self` closes `S ∪ Sᶜ = univ`.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11388

namespace Problems.Geometry.banach_tarski

def freegroup_paradoxical := @Problems.Geometry.banach_tarski.s11388

end Problems.Geometry.banach_tarski
