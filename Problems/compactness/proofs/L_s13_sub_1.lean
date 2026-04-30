import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- {neg φ, φ} is never satisfiable: no valuation can make both true simultaneously.
theorem s13_sub_1 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α) : ¬ Sat ({PropForm.neg φ, φ} : Set (PropForm α)) := by
  rintro ⟨v, hv⟩
  have h1 := hv (PropForm.neg φ) (by simp)
  have h2 := hv φ (by simp)
  simp [PropForm.eval, h2] at h1

end Problems.compactness
