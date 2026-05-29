-- Block-diagonal determinant: F = W ⊕ W' with both T-invariant, so in a basis
-- adapted to the decomposition T is block-diagonal, giving det T = det(T|W)·det(T|W').
-- Realize this as conjugation by `Submodule.prodEquivOfIsCompl`: the sub-goal
-- `t_conj_via_prodequiv` says T equals e ∘ (T|W ×ₗ T|W') ∘ e.symm; then
-- `LinearMap.det_conj` strips the conjugation and `LinearMap.det_prodMap` splits the product.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11422

namespace Problems.Geometry.banach_tarski

def det_eq_prod_det_restrict_invariant := @Problems.Geometry.banach_tarski.s11422

end Problems.Geometry.banach_tarski
