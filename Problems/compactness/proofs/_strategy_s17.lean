import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s17_s3_main_sub_2_sub_1
import Problems.compactness.proofs.L_s17_s3_main_sub_2_sub_2
import Problems.compactness.proofs.L_s17_s3_main_sub_2_sub_3

namespace Problems.compactness

theorem s17_s3_main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ N : Set (PropForm α), M ⊆ N →
      (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N) →
    ∀ p : PropForm α, p ∈ M ∨ PropForm.neg p ∈ M := by
  intro α M hfinsat hmax p
  by_cases hp : p ∈ M
  · exact Or.inl hp
  · obtain ⟨T', hT'sub, hT'fin, hT'unsat⟩ := s17_s3_main_sub_2_sub_1 M p hp hfinsat hmax
    have hMneg := s17_s3_main_sub_2_sub_2 M p hfinsat ⟨T', hT'sub, hT'fin, hT'unsat⟩
    exact Or.inr (s17_s3_main_sub_2_sub_3 M p hmax hMneg)

end Problems.compactness
