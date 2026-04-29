import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s17_s3_main_sub_1_sub_1
import Problems.compactness.proofs.L_s17_s3_main_sub_1_sub_2
import Problems.compactness.proofs.L_s17_s3_main_sub_1_sub_3
import Problems.compactness.proofs.L_s17_s3_main_sub_1_sub_4

namespace Problems.compactness

theorem s17_s3_main_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ p : PropForm α, p ∉ M →
        ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) := by
  intro α S hS
  have h_step : ∀ (c : Set (Set (PropForm α))), IsChain (· ⊆ ·) c →
      ∀ (T : Set (PropForm α)) (p : PropForm α),
      (∃ X₀ ∈ c, T ⊆ X₀) → (∃ X₁ ∈ c, p ∈ X₁) → ∃ X ∈ c, insert p T ⊆ X :=
    @s17_s3_main_sub_1_sub_1 α
  have h_cover : ∀ (c : Set (Set (PropForm α))), IsChain (· ⊆ ·) c → c.Nonempty →
      ∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ c → ∃ X ∈ c, T ⊆ X :=
    @s17_s3_main_sub_1_sub_2 α h_step
  have h_chain : ∀ C : Set (Set (PropForm α)), IsChain (· ⊆ ·) C → C.Nonempty →
      (∀ N ∈ C, S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
      S ⊆ ⋃₀ C ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T :=
    @s17_s3_main_sub_1_sub_3 α S h_cover
  exact @s17_s3_main_sub_1_sub_4 α S hS h_chain

end Problems.compactness
