import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s4_sub_1
import Problems.compactness.proofs.L_s4_sub_2
import Problems.compactness.proofs.L_s4_sub_3

namespace Problems.compactness

theorem s4 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α) : PropForm.neg φ ∈ M ↔ φ ∉ M := by
  constructor
  · intro h
    exact s4_sub_1 M hFinSat hMax φ h
  · intro hφ
    by_contra hNegφ
    obtain ⟨F₁, hF₁M, hF₁fin, hF₁unsat⟩ := s4_sub_2 M hFinSat hMax φ hφ
    obtain ⟨F₂, hF₂M, hF₂fin, hF₂unsat⟩ := s4_sub_2 M hFinSat hMax (PropForm.neg φ) hNegφ
    exact s4_sub_3 M hFinSat hMax φ F₁ hF₁M hF₁fin hF₁unsat F₂ hF₂M hF₂fin hF₂unsat

end Problems.compactness
