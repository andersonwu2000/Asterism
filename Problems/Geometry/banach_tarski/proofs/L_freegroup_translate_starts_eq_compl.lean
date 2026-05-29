-- Strip the set/pointwise-action layer, reducing the translation identity to a pure
-- FreeGroup word fact. `Set.ext` + `mem_smul_set_iff_inv_smul_mem` + `smul_eq_mul` rewrite
-- `w ∈ of i • W_{i⁻¹}` to `(of i)⁻¹ * w ∈ W_{i⁻¹}` and `w ∈ (W_i)ᶜ` to its head? ≠ guard;
-- the single sub-goal `head_inv_mul_iff` carries the head?-cancellation combinatorics.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11384

namespace Problems.Geometry.banach_tarski

def freegroup_translate_starts_eq_compl := @Problems.Geometry.banach_tarski.s11384

end Problems.Geometry.banach_tarski
