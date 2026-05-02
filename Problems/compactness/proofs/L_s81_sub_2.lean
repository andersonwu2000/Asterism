import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s81_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M → q ∈ M := by
  intro α M hMfinsat hneg p q hpq
  by_contra hq
  have hnegq : PropForm.neg q ∈ M := (hneg q).mpr hq
  have hTsub : ({PropForm.conj p q, PropForm.neg q} : Set (PropForm α)) ⊆ M := by
    intro x hx
    simp only [Set.mem_insert_iff, Set.mem_singleton_iff] at hx
    rcases hx with rfl | rfl
    · exact hpq
    · exact hnegq
  have hTfin : ({PropForm.conj p q, PropForm.neg q} : Set (PropForm α)).Finite :=
    (Set.finite_singleton _).insert _
  obtain ⟨v, hv⟩ := hMfinsat _ hTsub hTfin
  have hconj : PropForm.eval v (PropForm.conj p q) = true :=
    hv _ (Set.mem_insert _ _)
  have hneg_q : PropForm.eval v (PropForm.neg q) = true :=
    hv _ (Set.mem_insert_of_mem _ (Set.mem_singleton_iff.mpr rfl))
  simp only [PropForm.eval] at hconj hneg_q
  cases h : PropForm.eval v q
  · simp [h] at hconj
  · simp [h] at hneg_q

end Problems.compactness
