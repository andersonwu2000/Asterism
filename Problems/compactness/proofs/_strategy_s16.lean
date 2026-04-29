import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s16_s3_main_sub_4_sub_1
import Problems.compactness.proofs.L_s16_s3_main_sub_4_sub_2
import Problems.compactness.proofs.L_s16_s3_main_sub_4_sub_3
import Problems.compactness.proofs.L_s16_s3_main_sub_4_sub_4

namespace Problems.compactness

theorem s16_s3_main_sub_4 :
    ∀ {α : Type} (M : Set (PropForm α)),
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) →
    ∃ v : Valuation α, ∀ p : PropForm α, p ∈ M → PropForm.eval v p = true := by
  intro α M h_neg h_conj
  obtain ⟨v, hv⟩ := s16_s3_main_sub_4_sub_1 M
  use v
  have truth : ∀ p : PropForm α, p ∈ M ↔ PropForm.eval v p = true := by
    intro p
    induction p with
    | atom a     => exact s16_s3_main_sub_4_sub_2 M v hv a
    | neg p ih   => exact s16_s3_main_sub_4_sub_3 M v p h_neg ih
    | conj p q ihp ihq => exact s16_s3_main_sub_4_sub_4 M v p q h_conj ihp ihq
  intro p hp
  exact (truth p).mp hp

end Problems.compactness
