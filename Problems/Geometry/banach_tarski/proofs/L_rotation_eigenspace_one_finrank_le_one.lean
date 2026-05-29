-- Contrapositive route: assume `1 < finrank V` (V = ker(T-id), the fixed subspace).
-- V is T-invariant; so is its orthogonal complement Vᗮ (s11421). det T splits as
-- det(T|V)·det(T|Vᗮ) (s11422); det(T|V)=1 (T is id on V) and det T = 1 give det(T|Vᗮ)=1.
-- finrank V ≥ 2 ⇒ finrank Vᗮ ≤ 1, so the det-1 isometry T|Vᗮ is id (s11427), i.e. T fixes Vᗮ.
-- That collapses to T = refl (Vᗮ ⊆ V ∩ Vᗮ = 0 ⇒ Vᗮ = 0 ⇒ V = ⊤), contradicting hne.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11428

namespace Problems.Geometry.banach_tarski

def rotation_eigenspace_one_finrank_le_one := @Problems.Geometry.banach_tarski.s11428

end Problems.Geometry.banach_tarski
