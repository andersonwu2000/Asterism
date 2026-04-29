import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s15_s3_main_sub_4_sub_1 :
    ∀ {α : Type} (M : Set (PropForm α)),
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) →
    ∀ (v : Valuation α),
    (∀ a : α, v a = true ↔ PropForm.atom a ∈ M) →
    ∀ a : α, PropForm.atom a ∈ M ↔ PropForm.eval v (PropForm.atom a) = true := by
  intro α M _ _ v hv a
  simp only [PropForm.eval]
  exact (hv a).symm

end Problems.compactness
