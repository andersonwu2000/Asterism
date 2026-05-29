import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_head_inv_mul_iff

namespace Problems.Geometry.banach_tarski

open scoped Pointwise

-- translate_starts_eq_compl: left-multiply by of i sends W_{i,false} to (W_{i,true})ᶜ;
-- strips set/SMul layer via Set.ext + mem_smul_set_iff_inv_smul_mem, then closes with
-- head_inv_mul_iff
theorem translate_starts_eq_compl {α : Type*} [DecidableEq α] (i : α) :
    FreeGroup.of i • {w : FreeGroup α | (FreeGroup.toWord w).head? = some (i, false)}
      = {w : FreeGroup α | (FreeGroup.toWord w).head? = some (i, true)}ᶜ := by
  ext w
  rw [Set.mem_smul_set_iff_inv_smul_mem, smul_eq_mul, Set.mem_compl_iff,
    Set.mem_setOf_eq, Set.mem_setOf_eq]
  exact head_inv_mul_iff i w

end Problems.Geometry.banach_tarski

