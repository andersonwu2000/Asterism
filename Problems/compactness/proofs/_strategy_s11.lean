import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s11_s3_main_sub_4_sub_1
import Problems.compactness.proofs.L_s11_s3_main_sub_4_sub_2
import Problems.compactness.proofs.L_s11_s3_main_sub_4_sub_3

namespace Problems.compactness

theorem s11_s3_main_sub_4 :
    ∀ {α : Type} (M : Set (PropForm α)),
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) →
    ∃ v : Valuation α, ∀ p : PropForm α, p ∈ M → PropForm.eval v p = true := by
  intro α M neg_iff conj_iff
  obtain ⟨v, hv⟩ := s11_s3_main_sub_4_sub_1 M
  use v
  suffices h : ∀ p : PropForm α, PropForm.eval v p = true ↔ p ∈ M by
    intro p hp; exact (h p).mpr hp
  intro p
  induction p with
  | atom a => exact hv a
  | neg p ih => exact s11_s3_main_sub_4_sub_2 M v p neg_iff ih
  | conj p q ihp ihq => exact s11_s3_main_sub_4_sub_3 M v p q conj_iff ihp ihq

end Problems.compactness
