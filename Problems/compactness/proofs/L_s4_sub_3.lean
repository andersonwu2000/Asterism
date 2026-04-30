import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s4_sub_3 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α)
    (F₁ : Set (PropForm α)) (hF₁M : F₁ ⊆ M) (hF₁fin : F₁.Finite)
    (hF₁unsat : ¬Sat (insert φ F₁))
    (F₂ : Set (PropForm α)) (hF₂M : F₂ ⊆ M) (hF₂fin : F₂.Finite)
    (hF₂unsat : ¬Sat (insert (PropForm.neg φ) F₂)) : False := by
  sorry

end Problems.compactness
