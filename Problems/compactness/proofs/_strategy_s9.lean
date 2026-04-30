import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s9_sub_1
import Problems.compactness.proofs.L_s9_sub_2
import Problems.compactness.proofs.L_s9_sub_3
import Problems.compactness.proofs.L_s9_sub_4

namespace Problems.compactness

theorem s9 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α) : PropForm.neg φ ∈ M ↔ φ ∉ M := by
  have h1 : PropForm.neg φ ∈ M → φ ∉ M := s9_sub_1 M hFinSat hMax φ
  have h4 : φ ∉ M → PropForm.neg φ ∈ M := s9_sub_4 M hFinSat hMax φ
  exact ⟨h1, h4⟩

end Problems.compactness
