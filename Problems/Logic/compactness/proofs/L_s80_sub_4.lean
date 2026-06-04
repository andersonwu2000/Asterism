import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s80_sub_4 : ∀ {α : Type} (M : Set (PropForm α)) (v : Valuation α),
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) →
    ∀ p q : PropForm α,
    (p ∈ M ↔ PropForm.eval v p = true) →
    (q ∈ M ↔ PropForm.eval v q = true) →
    (PropForm.conj p q ∈ M ↔ PropForm.eval v (PropForm.conj p q) = true) := by
  intro α M v hconj p q ihp ihq
  show PropForm.conj p q ∈ M ↔ (PropForm.eval v p && PropForm.eval v q) = true
  rw [Bool.and_eq_true]
  exact (hconj p q).trans (and_congr ihp ihq)

end Problems.Logic.compactness
