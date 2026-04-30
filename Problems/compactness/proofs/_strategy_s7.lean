import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s7_sub_1
import Problems.compactness.proofs.L_s7_sub_2
import Problems.compactness.proofs.L_s7_sub_3

namespace Problems.compactness

theorem s7 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ ψ : PropForm α) : PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M) := by
  constructor
  · intro h
    exact ⟨s7_sub_1 M hFinSat hMax φ ψ h, s7_sub_2 M hFinSat hMax φ ψ h⟩
  · intro ⟨hφ, hψ⟩
    exact s7_sub_3 M hFinSat hMax φ ψ hφ hψ

end Problems.compactness
