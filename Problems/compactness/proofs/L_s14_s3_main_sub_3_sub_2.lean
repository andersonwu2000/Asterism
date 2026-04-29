import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s14_s3_main_sub_3_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M → q ∈ M := by
  intro α M hFinsat hNeg p q hcpq
  by_contra hq
  have hnq : PropForm.neg q ∈ M := (hNeg q).mpr hq
  have hSub : ({PropForm.conj p q, PropForm.neg q} : Set (PropForm α)) ⊆ M := by
    intro x hx
    simp only [Set.mem_insert_iff, Set.mem_singleton_iff] at hx
    rcases hx with rfl | rfl
    · exact hcpq
    · exact hnq
  obtain ⟨v, hv⟩ := hFinsat _ hSub ((Set.finite_singleton _).insert _)
  have hvcpq : PropForm.eval v (PropForm.conj p q) = true := by apply hv; simp
  have hvnq : PropForm.eval v (PropForm.neg q) = true := by apply hv; simp
  simp only [PropForm.eval] at hvcpq hvnq
  cases h : PropForm.eval v q with
  | false => simp [h] at hvcpq
  | true => simp [h] at hvnq

end Problems.compactness
