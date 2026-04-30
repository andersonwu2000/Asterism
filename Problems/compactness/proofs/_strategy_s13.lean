import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s13_sub_1
import Problems.compactness.proofs.L_s13_sub_2
import Problems.compactness.proofs.L_s13_sub_3
import Problems.compactness.proofs.L_s13_sub_4

namespace Problems.compactness

theorem s13 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α) : PropForm.neg φ ∈ M ↔ φ ∉ M := by
  constructor
  · intro h
    exact s13_sub_2 M hFinSat hMax φ h
  · intro hφ
    have h3 : ∀ T : Set (PropForm α), T ⊆ insert (PropForm.neg φ) M → T.Finite → Sat T :=
      s13_sub_3 M hFinSat hMax φ hφ
    exact s13_sub_4 M hFinSat hMax φ h3

end Problems.compactness
