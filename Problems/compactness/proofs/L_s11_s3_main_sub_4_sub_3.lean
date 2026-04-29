import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s11_s3_main_sub_4_sub_3 :
    ∀ {α : Type} (M : Set (PropForm α)) (v : Valuation α) (p q : PropForm α),
    (∀ p' q' : PropForm α, PropForm.conj p' q' ∈ M ↔ (p' ∈ M ∧ q' ∈ M)) →
    (PropForm.eval v p = true ↔ p ∈ M) →
    (PropForm.eval v q = true ↔ q ∈ M) →
    (PropForm.eval v (PropForm.conj p q) = true ↔ PropForm.conj p q ∈ M) := by
  intro α M v p q hconj ihp ihq
  simp only [PropForm.eval, Bool.and_eq_true]
  constructor
  · rintro ⟨hp, hq⟩
    exact (hconj p q).mpr ⟨ihp.mp hp, ihq.mp hq⟩
  · intro h
    exact ⟨ihp.mpr ((hconj p q).mp h).1, ihq.mpr ((hconj p q).mp h).2⟩

end Problems.compactness
