import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- `lift f` is injective ⇔ trivial kernel; reduce to `lift f w = 1 → w = 1`.
-- `lift f w` equals the product over `toWord w` (representation lemma, via `lift_mk`),
-- so if `w ≠ 1` then `toWord w ≠ []` and the hypothesis `h` forbids that product = 1.
theorem s11411
    {α : Type*} [DecidableEq α] {G : Type*} [Group G] (f : α → G)
    (h : ∀ w : FreeGroup α, FreeGroup.toWord w ≠ [] →
        ((FreeGroup.toWord w).map
            (fun x : α × Bool => if x.2 then f x.1 else (f x.1)⁻¹)).prod ≠ 1) :
    Function.Injective (FreeGroup.lift f)  := by
  have lift_eq_word_prod : ∀ w : FreeGroup α,
      (FreeGroup.lift f) w = ((FreeGroup.toWord w).map
        (fun x : α × Bool => if x.2 then f x.1 else (f x.1)⁻¹)).prod := by
    intro w
    conv_lhs => rw [← FreeGroup.mk_toWord (x := w)]
    rw [FreeGroup.lift_mk]
    congr 1
    apply List.map_congr_left
    intro x _
    cases x.2 <;> rfl
  rw [injective_iff_map_eq_one (FreeGroup.lift f)]
  intro w hw
  by_contra hne
  have hword : FreeGroup.toWord w ≠ [] := by
    intro hc
    exact hne (FreeGroup.toWord_injective (by rw [hc, FreeGroup.toWord_one]))
  exact h w hword (by rw [← lift_eq_word_prod w]; exact hw)

end Problems.Geometry.banach_tarski
