import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s13_s3_main_sub_1_sub_1
import Problems.compactness.proofs.L_s13_s3_main_sub_1_sub_2
import Problems.compactness.proofs.L_s13_s3_main_sub_1_sub_3

namespace Problems.compactness

theorem s13_s3_main_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ p : PropForm α, p ∉ M →
        ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) := by
  intro α S hS
  have h1 : ∀ (c : Set (Set (PropForm α))), c.Nonempty → IsChain (· ⊆ ·) c →
      ∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ c → ∃ X ∈ c, T ⊆ X :=
    @s13_s3_main_sub_1_sub_1 α
  have h2 : ∀ c : Set (Set (PropForm α)), c.Nonempty → IsChain (· ⊆ ·) c →
      (∀ X ∈ c, S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
      S ⊆ ⋃₀ c ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ c → T.Finite → Sat T :=
    @s13_s3_main_sub_1_sub_2 α S h1
  exact @s13_s3_main_sub_1_sub_3 α S hS h2

end Problems.compactness
