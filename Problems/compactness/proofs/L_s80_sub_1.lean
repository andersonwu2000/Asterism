import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s80_sub_1 : ∀ {α : Type} (M : Set (PropForm α)),
    ∃ v : Valuation α, ∀ a : α, v a = true ↔ PropForm.atom a ∈ M := by
  intro α M
  classical
  exact ⟨fun a => decide (PropForm.atom a ∈ M), fun a => by simp⟩

end Problems.compactness
