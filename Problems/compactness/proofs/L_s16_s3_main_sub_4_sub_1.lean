import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s16_s3_main_sub_4_sub_1 :
    ∀ {α : Type} (M : Set (PropForm α)),
    ∃ v : Valuation α, ∀ a : α, v a = true ↔ PropForm.atom a ∈ M := by
  intro α M
  classical
  refine ⟨fun a => if PropForm.atom a ∈ M then true else false, fun a => ?_⟩
  by_cases h : PropForm.atom a ∈ M <;> simp [h]

end Problems.compactness
