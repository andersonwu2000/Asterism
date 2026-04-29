import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s16_s3_main_sub_4_sub_4 :
    ∀ {α : Type} (M : Set (PropForm α)) (v : Valuation α) (p q : PropForm α),
    (∀ p' q' : PropForm α, PropForm.conj p' q' ∈ M ↔ (p' ∈ M ∧ q' ∈ M)) →
    (p ∈ M ↔ PropForm.eval v p = true) →
    (q ∈ M ↔ PropForm.eval v q = true) →
    (PropForm.conj p q ∈ M ↔ PropForm.eval v (PropForm.conj p q) = true) := by
  intro α M v p q h_conj hp hq
  simp only [h_conj, PropForm.eval, Bool.and_eq_true, hp, hq]

end Problems.compactness
