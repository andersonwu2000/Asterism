import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s5_s3_main_sub_2_sub_1
import Problems.compactness.proofs.L_s5_s3_main_sub_2_sub_2
import Problems.compactness.proofs.L_s5_s3_main_sub_2_sub_3
import Problems.compactness.proofs.L_s5_s3_main_sub_2_sub_4

namespace Problems.compactness

theorem s5_s3_main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M := by
  intro α M hfinsat hmax p
  have h1 : PropForm.neg p ∈ M → p ∉ M :=
    s5_s3_main_sub_2_sub_1 M hfinsat hmax p
  have h2 : ∀ (q : PropForm α) (T : Set (PropForm α)),
      Sat T → ¬Sat (insert q T) → Sat (insert (PropForm.neg q) T) :=
    s5_s3_main_sub_2_sub_2 M hfinsat hmax
  have h3 : ∀ q : PropForm α,
      ¬(∀ T : Set (PropForm α), T ⊆ insert q M → T.Finite → Sat T) →
      ∃ T₁ : Set (PropForm α), T₁ ⊆ M ∧ T₁.Finite ∧ ¬Sat (insert q T₁) :=
    s5_s3_main_sub_2_sub_3 M hfinsat hmax
  have h4 : p ∉ M → PropForm.neg p ∈ M :=
    s5_s3_main_sub_2_sub_4 M hfinsat hmax p
  exact ⟨h1, h4⟩

end Problems.compactness
