import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s81_sub_1 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M → p ∈ M := by
  intro α M hMfinsat hneg p q hpq
  by_contra hp
  have hnegp : PropForm.neg p ∈ M := (hneg p).mpr hp
  have hT : ({PropForm.conj p q, PropForm.neg p} : Set (PropForm α)) ⊆ M := by
    intro x hx
    simp only [Set.mem_insert_iff, Set.mem_singleton_iff] at hx
    rcases hx with rfl | rfl <;> assumption
  have hTfin : ({PropForm.conj p q, PropForm.neg p} : Set (PropForm α)).Finite :=
    (Set.finite_singleton _).insert _
  obtain ⟨v, hv⟩ := hMfinsat _ hT hTfin
  have h1 : PropForm.eval v (PropForm.conj p q) = true := hv (PropForm.conj p q) (by simp)
  have h2 : PropForm.eval v (PropForm.neg p) = true := hv (PropForm.neg p) (by simp)
  simp [PropForm.eval] at h1
  simp [PropForm.eval, h1.1] at h2

end Problems.compactness
