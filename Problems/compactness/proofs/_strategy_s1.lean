import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s1_sub_1
import Problems.compactness.proofs.L_s1_sub_2
import Problems.compactness.proofs.L_s1_sub_3
import Problems.compactness.proofs.L_s1_sub_4

namespace Problems.compactness

theorem s1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) → Sat S := by
  intro α S hS
  have h1 : ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      (∀ φ : PropForm α, φ ∉ M →
        ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T) :=
    s1_sub_1 S hS
  obtain ⟨M, hSM, hFinSatM, hMaxM⟩ := h1
  have h2 : ∀ φ : PropForm α, PropForm.neg φ ∈ M ↔ φ ∉ M :=
    fun φ => s1_sub_2 M hFinSatM hMaxM φ
  have h3 : ∀ φ ψ : PropForm α, PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M) :=
    fun φ ψ => s1_sub_3 M hFinSatM hMaxM φ ψ
  have h4 : ∃ v : Valuation α, ∀ φ : PropForm α, φ ∈ M → PropForm.eval v φ = true :=
    s1_sub_4 M h2 h3
  obtain ⟨v, hv⟩ := h4
  exact ⟨v, fun φ hφ => hv φ (hSM hφ)⟩

end Problems.compactness
