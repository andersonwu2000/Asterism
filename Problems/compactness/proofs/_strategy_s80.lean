import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s80_sub_1
import Problems.compactness.proofs.L_s80_sub_2
import Problems.compactness.proofs.L_s80_sub_3
import Problems.compactness.proofs.L_s80_sub_4

namespace Problems.compactness

theorem s80 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) →
    ∃ v : Valuation α, ∀ p : PropForm α, p ∈ M → PropForm.eval v p = true := by
  intro α M hneg hconj
  obtain ⟨v, hv_atom⟩ := s80_sub_1 M
  have hbicond : ∀ p : PropForm α, p ∈ M ↔ PropForm.eval v p = true := by
    intro p
    induction p with
    | atom a     => exact s80_sub_2 M v hv_atom a
    | neg p ih   => exact s80_sub_3 M v hneg p ih
    | conj p q ihp ihq => exact s80_sub_4 M v hconj p q ihp ihq
  exact ⟨v, fun p hp => (hbicond p).mp hp⟩

end Problems.compactness
