import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

open Classical

theorem s11_sub_1 {α : Type} (M : Set (PropForm α)) :
    ∃ v : Valuation α, ∀ a : α, v a = true ↔ PropForm.atom a ∈ M := by
  use fun a => if PropForm.atom a ∈ M then true else false
  intro a
  by_cases h : PropForm.atom a ∈ M <;> simp [h]

end Problems.compactness
