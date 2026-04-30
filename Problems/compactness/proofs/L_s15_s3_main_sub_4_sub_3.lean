import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s15_s3_main_sub_4_sub_3 :
    ∀ {α : Type} (M : Set (PropForm α)),
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) →
    ∀ (v : Valuation α) (p q : PropForm α),
    (p ∈ M ↔ PropForm.eval v p = true) →
    (q ∈ M ↔ PropForm.eval v q = true) →
    (PropForm.conj p q ∈ M ↔ PropForm.eval v (PropForm.conj p q) = true) := by
  intro α M h_neg h_conj v p q hp hq
  constructor
  · intro hmem
    obtain ⟨hpm, hqm⟩ := (h_conj p q).mp hmem
    simp [PropForm.eval, hp.mp hpm, hq.mp hqm]
  · intro heval
    apply (h_conj p q).mpr
    simp [PropForm.eval] at heval
    exact ⟨hp.mpr heval.1, hq.mpr heval.2⟩

end Problems.compactness
