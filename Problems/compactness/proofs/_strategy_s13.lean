import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s13_s3_main_sub_1_sub_1
import Problems.compactness.proofs.L_s13_s3_main_sub_1_sub_2
import Problems.compactness.proofs.L_s13_s3_main_sub_1_sub_3

namespace Problems.compactness

theorem s13_s3_main_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α), M ⊆ N →
        (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N := by
  intro α S hfinsat
  have h_cover : ∀ (C : Set (Set (PropForm α))) (T : Set (PropForm α)),
      IsChain (· ⊆ ·) C → C.Nonempty → T.Finite → T ⊆ ⋃₀ C → ∃ M ∈ C, T ⊆ M :=
    @s13_s3_main_sub_1_sub_1 α
  have hchain_bound : ∀ C : Set (Set (PropForm α)),
      IsChain (· ⊆ ·) C → C.Nonempty →
      (∀ M ∈ C, S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
      ∃ ub : Set (PropForm α),
        (S ⊆ ub ∧ ∀ T : Set (PropForm α), T ⊆ ub → T.Finite → Sat T) ∧
        ∀ M ∈ C, M ⊆ ub :=
    fun C hchain hne hCF => s13_s3_main_sub_1_sub_2 S C h_cover hchain hne hCF
  exact s13_s3_main_sub_1_sub_3 S hfinsat hchain_bound

end Problems.compactness
