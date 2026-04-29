import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s15_s3_main_sub_4_sub_1
import Problems.compactness.proofs.L_s15_s3_main_sub_4_sub_2
import Problems.compactness.proofs.L_s15_s3_main_sub_4_sub_3

namespace Problems.compactness

theorem s15_s3_main_sub_4 :
    ∀ {α : Type} (M : Set (PropForm α)),
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) →
    ∃ v : Valuation α, ∀ p : PropForm α, p ∈ M → PropForm.eval v p = true := by
  intro α M h_neg h_conj
  letI : ∀ a : α, Decidable (PropForm.atom a ∈ M) := fun _ => Classical.propDecidable _
  let v : Valuation α := fun a => if PropForm.atom a ∈ M then true else false
  have hv_atom : ∀ a : α, v a = true ↔ PropForm.atom a ∈ M := fun a => by
    simp only [v]
    by_cases h : PropForm.atom a ∈ M <;> simp [h]
  have truth : ∀ p : PropForm α, p ∈ M ↔ PropForm.eval v p = true := fun p => by
    induction p with
    | atom a     => exact s15_s3_main_sub_4_sub_1 M h_neg h_conj v hv_atom a
    | neg p ih   => exact s15_s3_main_sub_4_sub_2 M h_neg h_conj v p ih
    | conj p q ihp ihq => exact s15_s3_main_sub_4_sub_3 M h_neg h_conj v p q ihp ihq
  exact ⟨v, fun p hp => (truth p).mp hp⟩

end Problems.compactness
