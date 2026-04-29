import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s24_s4_main_sub_3_sub_1
import Problems.compactness.proofs.L_s24_s4_main_sub_3_sub_2
import Problems.compactness.proofs.L_s24_s4_main_sub_3_sub_3

namespace Problems.compactness

theorem s24_s4_main_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M) := by
  intro α M hFinsat hNeg p q
  have h1 : PropForm.conj p q ∈ M → p ∈ M :=
    s24_s4_main_sub_3_sub_1 M hFinsat hNeg p q
  have h2 : PropForm.conj p q ∈ M → q ∈ M :=
    s24_s4_main_sub_3_sub_2 M hFinsat hNeg p q
  have h3 : p ∈ M → q ∈ M → PropForm.conj p q ∈ M :=
    s24_s4_main_sub_3_sub_3 M hFinsat hNeg p q
  exact ⟨fun hcpq => ⟨h1 hcpq, h2 hcpq⟩, fun ⟨hp, hq⟩ => h3 hp hq⟩

end Problems.compactness
