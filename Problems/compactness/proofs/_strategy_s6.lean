import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s6_s3_main_sub_1_sub_1
import Problems.compactness.proofs.L_s6_s3_main_sub_1_sub_2
import Problems.compactness.proofs.L_s6_s3_main_sub_1_sub_3
import Problems.compactness.proofs.L_s6_s3_main_sub_1_sub_4

namespace Problems.compactness

theorem s6_s3_main_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ p : PropForm α, p ∉ M →
        ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) := by
  intro α S hS
  have h_cover : ∀ (C : Set (Set (PropForm α))), IsChain (· ⊆ ·) C → C.Nonempty →
      ∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ C → ∃ N ∈ C, T ⊆ N :=
    s6_s3_main_sub_1_sub_1
  have hchainBound : ∀ (C : Set (Set (PropForm α))), IsChain (· ⊆ ·) C → C.Nonempty →
      (∀ N ∈ C, S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
      S ⊆ ⋃₀ C ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T :=
    fun C hC hne hCp => s6_s3_main_sub_1_sub_2 S C hC hne hCp (h_cover C hC hne)
  obtain ⟨M, hSM, hMfinsat, hMmax⟩ := s6_s3_main_sub_1_sub_3 S hS hchainBound
  have h_pnotM : ∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) :=
    s6_s3_main_sub_1_sub_4 S M hSM hMfinsat hMmax
  exact ⟨M, hSM, hMfinsat, h_pnotM⟩

end Problems.compactness
