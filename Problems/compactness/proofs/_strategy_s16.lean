import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s16_s3_main_sub_2_sub_1
import Problems.compactness.proofs.L_s16_s3_main_sub_2_sub_2

namespace Problems.compactness

theorem s16_s3_main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ N : Set (PropForm α), M ⊆ N →
      (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N) →
    ∀ p : PropForm α, p ∈ M ∨ PropForm.neg p ∈ M := by
  intro α M hfsat hmax p
  by_cases hp : ∀ T : Set (PropForm α), T ⊆ M ∪ {p} → T.Finite → Sat T
  · exact Or.inl (s16_s3_main_sub_2_sub_2 M p hfsat hmax hp)
  · have hfsat_neg : ∀ T : Set (PropForm α), T ⊆ M ∪ {PropForm.neg p} → T.Finite → Sat T :=
      s16_s3_main_sub_2_sub_1 M p hfsat hp
    exact Or.inr (s16_s3_main_sub_2_sub_2 M (PropForm.neg p) hfsat hmax hfsat_neg)

end Problems.compactness
