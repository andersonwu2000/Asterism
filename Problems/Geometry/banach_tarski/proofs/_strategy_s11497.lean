import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- (of 1)⁻¹^m reduces to the constant word `replicate m (1, false)`, whose head
-- (when nonempty) has first component 1 ≠ 0; the empty case (m = 0) is `none`.
-- Direct free-group computation: (of 1)⁻¹ = mk [(1,false)], so the power is
-- mk (replicate m (1,false)), and `reduce` fixes the already-reduced replicate.
theorem s11497 : ∀ m : ℕ,
    ¬ (FreeGroup.toWord ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹ ^ m)).head?.map Prod.fst
      = some 0  := by
  intro m
  have hgen : ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹) = FreeGroup.mk [(1, false)] := by
    rw [FreeGroup.of, FreeGroup.inv_mk]; rfl
  have hred : ∀ k : ℕ,
      FreeGroup.reduce (List.replicate k (1, false) : List (Fin 2 × Bool))
        = List.replicate k (1, false) := by
    intro k
    induction k with
    | zero => rfl
    | succ k ih =>
      rw [List.replicate_succ, FreeGroup.reduce.cons, ih]
      cases k with
      | zero => rfl
      | succ j => rw [List.replicate_succ]; simp
  have hpow : ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹) ^ m
      = FreeGroup.mk (List.replicate m (1, false)) := by
    induction m with
    | zero => rfl
    | succ k ih =>
      rw [pow_succ, ih, hgen, FreeGroup.mul_mk, ← List.replicate_succ']
  have hw : FreeGroup.toWord ((FreeGroup.of 1 : FreeGroup (Fin 2))⁻¹ ^ m)
      = List.replicate m (1, false) := by
    rw [hpow, FreeGroup.toWord_mk, hred]
  rw [hw]
  cases m with
  | zero => simp
  | succ n => simp [List.replicate_succ]

end Problems.Geometry.banach_tarski
