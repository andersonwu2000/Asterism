import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_reduce_cons_head_of_reduced

namespace Problems.Geometry.banach_tarski

-- Strip the group layer, then reduce to a pure `reduce`-of-cons head fact.
-- `hmul` rewrites `(of i)⁻¹ * w` to `mk ((i,false) :: toWord w)` (via `inv_mk`/`mul_mk`)
-- so its `toWord` is `reduce ((i,false) :: toWord w)` — the group algebra is discharged inline.
-- The remaining content is the single sub-goal `reduce_cons_head_of_reduced`: for an already
-- reduced list `L`, prepending a letter `x` keeps `x` as head iff `L` does not start with `x`'s
-- inverse `(x.1, !x.2)`. Instantiated at `x = (i,false)`, `L = toWord w` (reduced by
-- `reduce_toWord`), `(x.1, !x.2) = (i, true)`, closing the parent.
theorem s11385 {α : Type*} [DecidableEq α] (i : α) (w : FreeGroup α) :
    (FreeGroup.toWord ((FreeGroup.of i)⁻¹ * w)).head? = some (i, false)
      ↔ (FreeGroup.toWord w).head? ≠ some (i, true)  := by
  have hmul : FreeGroup.toWord ((FreeGroup.of i)⁻¹ * w)
      = FreeGroup.reduce ((i, false) :: FreeGroup.toWord w) := by
    have hinv : (FreeGroup.of i)⁻¹ = FreeGroup.mk [(i, false)] := by
      rw [show (FreeGroup.of i) = FreeGroup.mk [(i, true)] from rfl, FreeGroup.inv_mk]; rfl
    conv_lhs => rw [hinv, ← FreeGroup.mk_toWord (x := w), FreeGroup.mul_mk]
    rw [FreeGroup.toWord_mk]; rfl
  rw [hmul]
  have h := reduce_cons_head_of_reduced (i, false) (FreeGroup.toWord w)
    (FreeGroup.reduce_toWord w)
  simpa using h

end Problems.Geometry.banach_tarski
