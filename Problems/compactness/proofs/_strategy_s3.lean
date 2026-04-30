import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s3_sub_1
import Problems.compactness.proofs.L_s3_sub_2
import Problems.compactness.proofs.L_s3_sub_3
import Problems.compactness.proofs.L_s3_sub_4

namespace Problems.compactness

theorem s3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) → Sat S := by
  intro α S hS
  have h_chain_bound : ∀ C : Set (Set (PropForm α)), IsChain (· ⊆ ·) C →
      (∀ s ∈ C, ∀ T : Set (PropForm α), T ⊆ s → T.Finite → Sat T) →
      ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T :=
    fun C hchain hfinsat T hT hfin => s3_sub_1 C hchain hfinsat T hT hfin
  obtain ⟨M, hSM, hfinsat_M, hmax_M⟩ := s3_sub_2 S hS h_chain_bound
  obtain ⟨hneg, hconj⟩ := s3_sub_3 M hfinsat_M hmax_M
  exact s3_sub_4 S M hSM hneg hconj

end Problems.compactness
