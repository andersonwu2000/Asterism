import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s2_sub_1
import Problems.compactness.proofs.L_s2_sub_2
import Problems.compactness.proofs.L_s2_sub_3
import Problems.compactness.proofs.L_s2_sub_4
import Problems.compactness.proofs.L_s2_sub_5

namespace Problems.compactness

theorem s2 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) → Sat S := by
  intro α S hfinsat
  -- Step 1: extend S to a maximal finitely-satisfiable superset M
  obtain ⟨M, hM_super, hM_finsat, hM_max⟩ := s2_sub_1 S hfinsat
  -- Step 2: M is complete (contains p or neg p for every formula)
  have hM_complete : ∀ p : PropForm α, p ∈ M ∨ PropForm.neg p ∈ M :=
    s2_sub_2 M hM_finsat hM_max
  -- Step 3: negation closure — neg p ∈ M iff p ∉ M
  have hM_neg : ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M :=
    s2_sub_3 M hM_finsat hM_complete
  -- Step 4: conjunction closure — conj p q ∈ M iff p ∈ M and q ∈ M
  have hM_conj : ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M) :=
    s2_sub_4 M hM_finsat hM_complete
  -- Step 5: canonical valuation satisfies all of M
  obtain ⟨v, hv⟩ := s2_sub_5 M hM_finsat hM_complete hM_neg hM_conj
  -- S ⊆ M, so v satisfies all of S
  exact ⟨v, fun p hp => hv p (hM_super hp)⟩

end Problems.compactness
