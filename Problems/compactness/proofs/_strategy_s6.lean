import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s6_sub_1
import Problems.compactness.proofs.L_s6_sub_2
import Problems.compactness.proofs.L_s6_sub_3

namespace Problems.compactness

theorem s6 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ ψ : PropForm α) : PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M) := by
  have h_left : PropForm.conj φ ψ ∈ M → φ ∈ M := s6_sub_1 M hFinSat hMax φ ψ
  have h_right : PropForm.conj φ ψ ∈ M → ψ ∈ M := s6_sub_2 M hFinSat hMax φ ψ
  have h_intro : φ ∈ M → ψ ∈ M → PropForm.conj φ ψ ∈ M := s6_sub_3 M hFinSat hMax φ ψ
  constructor
  · intro h
    exact ⟨h_left h, h_right h⟩
  · intro ⟨hφ, hψ⟩
    exact h_intro hφ hψ

end Problems.compactness
