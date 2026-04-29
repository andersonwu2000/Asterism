import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s21_s4_main_sub_2_sub_1
import Problems.compactness.proofs.L_s21_s4_main_sub_2_sub_2
import Problems.compactness.proofs.L_s21_s4_main_sub_2_sub_3

namespace Problems.compactness

theorem s21_s4_main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ M' : Set (PropForm α), M ⊆ M' →
      (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M') →
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M := by
  intro α M hfinsat hmax p
  have h1 : PropForm.neg p ∈ M → p ∉ M :=
    s21_s4_main_sub_2_sub_1 M hfinsat p
  have _h2 : ∀ q : PropForm α, q ∉ M →
      ∃ T : Set (PropForm α), T ⊆ M ∧ T.Finite ∧ ¬Sat (T ∪ {q}) :=
    s21_s4_main_sub_2_sub_2 M hfinsat hmax
  have h3 : p ∉ M → PropForm.neg p ∈ M :=
    s21_s4_main_sub_2_sub_3 M hfinsat hmax p
  exact Iff.intro h1 h3

end Problems.compactness
