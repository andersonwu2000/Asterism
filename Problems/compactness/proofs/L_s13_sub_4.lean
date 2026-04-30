import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Fin-sat of insert (neg φ) M forces neg φ ∈ M, by contrapositive of hMax.
theorem s13_sub_4 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α)
    (h : ∀ T : Set (PropForm α), T ⊆ insert (PropForm.neg φ) M → T.Finite → Sat T) :
    PropForm.neg φ ∈ M := by
  by_contra hne
  exact hMax (PropForm.neg φ) hne h

end Problems.compactness
