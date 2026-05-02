import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s87_sub_2 : ∀ {α : Type} (C : Set (Set (PropForm α))),
    (∀ X ∈ C, ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
    ∀ T : Set (PropForm α), T.Finite →
    (∃ X ∈ C, T ⊆ X) →
    Sat T := by
  intro α C hfinsat T hTfin hcov
  obtain ⟨X, hXC, hTX⟩ := hcov
  exact hfinsat X hXC T hTX hTfin

end Problems.compactness
