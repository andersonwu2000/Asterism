import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s9_sub_2
import Problems.compactness.proofs.L_s9_sub_3

namespace Problems.compactness

-- Backward: φ ∉ M → neg φ ∈ M, via hMax contrapositive + s9_sub_2 + s9_sub_3.
theorem s9_sub_4 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α) : φ ∉ M → PropForm.neg φ ∈ M := by
  intro hφ
  by_contra hneg
  apply hMax (PropForm.neg φ) hneg
  obtain ⟨T₀, hT₀M, hT₀fin, hT₀bad⟩ := s9_sub_2 M hFinSat hMax φ hφ
  intro T hTins hTfin
  by_cases h : PropForm.neg φ ∈ T
  · have hT'sub : T \ {PropForm.neg φ} ⊆ M := by
      intro x hx
      simp only [Set.mem_diff, Set.mem_singleton_iff] at hx
      obtain ⟨hxT, hxne⟩ := hx
      rcases Set.mem_insert_iff.mp (hTins hxT) with rfl | hxM
      · exact absurd rfl hxne
      · exact hxM
    have hT'fin : (T \ {PropForm.neg φ}).Finite := hTfin.subset Set.diff_subset
    have hSat := s9_sub_3 M hFinSat hMax φ T₀ hT₀M hT₀fin hT₀bad
                           (T \ {PropForm.neg φ}) hT'sub hT'fin
    rwa [Set.insert_diff_singleton, Set.insert_eq_of_mem h] at hSat
  · apply hFinSat T _ hTfin
    intro x hxT
    rcases Set.mem_insert_iff.mp (hTins hxT) with rfl | hxM
    · exact absurd hxT h
    · exact hxM

end Problems.compactness
