import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s83_sub_1 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, p ∉ M →
      ∃ T' : Set (PropForm α), T' ⊆ insert p M ∧ T'.Finite ∧ ¬Sat T' := by
  intro α M _hfinsat hmax p hp
  have h := hmax p hp
  push_neg at h
  exact h

end Problems.compactness
