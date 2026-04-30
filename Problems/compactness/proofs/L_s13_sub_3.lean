import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- If φ ∉ M, then insert (neg φ) M is finitely satisfiable.
-- Proof: maximality gives a finite witness T' ⊆ M with T' ∪ {φ} unsat;
-- any valuation satisfying T' must set φ false, hence satisfies neg φ.
theorem s13_sub_3 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α) (hφ : φ ∉ M) :
    ∀ T : Set (PropForm α), T ⊆ insert (PropForm.neg φ) M → T.Finite → Sat T := by
  sorry

end Problems.compactness
