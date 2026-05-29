import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_head_inv_mul_iff

namespace Problems.Geometry.banach_tarski

open scoped Pointwise

-- Strip the set/pointwise-action layer, reducing the translation identity to a pure
-- FreeGroup word fact. `Set.ext` + `mem_smul_set_iff_inv_smul_mem` + `smul_eq_mul` rewrite
-- `w ∈ of i • W_{i⁻¹}` to `(of i)⁻¹ * w ∈ W_{i⁻¹}` and `w ∈ (W_i)ᶜ` to its head? ≠ guard;
-- the single sub-goal `head_inv_mul_iff` carries the head?-cancellation combinatorics.
theorem s11384 {α : Type*} [DecidableEq α] (i : α) :

    FreeGroup.of i •
        {w : FreeGroup α | (FreeGroup.toWord w).head? = some (i, false)}
      = {w : FreeGroup α | (FreeGroup.toWord w).head? = some (i, true)}ᶜ  := by
  ext w
  rw [Set.mem_smul_set_iff_inv_smul_mem, smul_eq_mul, Set.mem_compl_iff,
    Set.mem_setOf_eq, Set.mem_setOf_eq]
  exact head_inv_mul_iff i w


end Problems.Geometry.banach_tarski

