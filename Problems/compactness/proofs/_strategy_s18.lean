import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s18_s3_main_sub_2_sub_1
import Problems.compactness.proofs.L_s18_s3_main_sub_2_sub_2
import Problems.compactness.proofs.L_s18_s3_main_sub_2_sub_3

namespace Problems.compactness

theorem s18_s3_main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ N : Set (PropForm α), M ⊆ N →
      (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N) →
    ∀ p : PropForm α, p ∈ M ∨ PropForm.neg p ∈ M := by
  intro α M hfinsat hmax p
  by_contra h
  push_neg at h
  obtain ⟨hnp, hnnp⟩ := h
  have h1p : ¬(∀ T : Set (PropForm α), T ⊆ M ∪ {p} → T.Finite → Sat T) :=
    s18_s3_main_sub_2_sub_1 M p hfinsat hmax hnp
  obtain ⟨T₀, hT₀sub, hT₀fin, hT₀unsat⟩ :=
    s18_s3_main_sub_2_sub_2 M p hfinsat h1p
  have h1np : ¬(∀ T : Set (PropForm α), T ⊆ M ∪ {PropForm.neg p} → T.Finite → Sat T) :=
    s18_s3_main_sub_2_sub_1 M (PropForm.neg p) hfinsat hmax hnnp
  obtain ⟨T₁, hT₁sub, hT₁fin, hT₁unsat⟩ :=
    s18_s3_main_sub_2_sub_2 M (PropForm.neg p) hfinsat h1np
  exact s18_s3_main_sub_2_sub_3 M p hfinsat
    ⟨T₀, hT₀sub, hT₀fin, hT₀unsat⟩ ⟨T₁, hT₁sub, hT₁fin, hT₁unsat⟩

end Problems.compactness
