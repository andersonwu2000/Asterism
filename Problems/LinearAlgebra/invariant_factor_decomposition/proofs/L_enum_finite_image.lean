-- Direct finiteness plumbing: enumerate the image `Finset.univ.image f` via its
-- `Finset.equivFin : ↥S ≃ Fin S.card`. q = the symm-image coercion (injective by
-- subtype/equiv injectivity), key a = equivFin ⟨f a, _⟩ (f a = q (key a) by symm_apply_apply),
-- surjectivity from each enumerated value lying in the image Finset.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11584

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def enum_finite_image := @Problems.LinearAlgebra.invariant_factor_decomposition.s11584

end Problems.LinearAlgebra.invariant_factor_decomposition
