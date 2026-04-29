import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s15_s3_main_sub_4_sub_2 :
    ∀ {α : Type} (M : Set (PropForm α)),
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) →
    ∀ (v : Valuation α) (p : PropForm α),
    (p ∈ M ↔ PropForm.eval v p = true) →
    (PropForm.neg p ∈ M ↔ PropForm.eval v (PropForm.neg p) = true) := by
  intro α M h_neg _ v p hp
  simp only [PropForm.eval]
  constructor
  · intro hnegM
    have hpM : p ∉ M := (h_neg p).mp hnegM
    cases hb : PropForm.eval v p with
    | true => exact absurd (hp.mpr hb) hpM
    | false => simp [hb]
  · intro heval
    apply (h_neg p).mpr
    intro hpM
    have hpT : PropForm.eval v p = true := hp.mp hpM
    rw [hpT] at heval
    simp at heval

end Problems.compactness
