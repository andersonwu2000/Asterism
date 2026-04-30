import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s14_s3_main_sub_1_sub_1
import Problems.compactness.proofs.L_s14_s3_main_sub_1_sub_2
import Problems.compactness.proofs.L_s14_s3_main_sub_1_sub_3

namespace Problems.compactness

theorem s14_s3_main_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α), M ⊆ N →
        (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N := by
  intro α S hfinsat
  have h1 : ∀ (c : Set (Set (PropForm α))), IsChain (· ⊆ ·) c → c.Nonempty →
      ∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ c → ∃ M ∈ c, T ⊆ M :=
    fun c hchain hne T hTfin hTc => s14_s3_main_sub_1_sub_1 c hchain hne T hTfin hTc
  have h2 : ∀ c : Set (Set (PropForm α)), c.Nonempty → IsChain (· ⊆ ·) c →
      (∀ M ∈ c, S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
      S ⊆ ⋃₀ c ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ c → T.Finite → Sat T :=
    fun c hne hchain hc => s14_s3_main_sub_1_sub_2 S c hne hchain hc (h1 c hchain hne)
  exact s14_s3_main_sub_1_sub_3 S hfinsat h2

end Problems.compactness
