import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s9_s3_main_sub_3_sub_1 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M → p ∈ M := by
  intro α M hFinsat hNeg p q hpq
  by_contra hp
  have hnegp : PropForm.neg p ∈ M := (hNeg p).mpr hp
  have hSubset : ({PropForm.conj p q, PropForm.neg p} : Set (PropForm α)) ⊆ M := by
    simp only [Set.insert_subset_iff, Set.singleton_subset_iff]
    exact ⟨hpq, hnegp⟩
  have hFin : ({PropForm.conj p q, PropForm.neg p} : Set (PropForm α)).Finite := by
    apply Set.Finite.insert
    exact Set.finite_singleton _
  obtain ⟨v, hv⟩ := hFinsat _ hSubset hFin
  have hv1 : PropForm.eval v (PropForm.conj p q) = true :=
    hv (PropForm.conj p q) (by simp)
  have hv2 : PropForm.eval v (PropForm.neg p) = true :=
    hv (PropForm.neg p) (by simp)
  simp only [PropForm.eval] at hv1 hv2
  cases hpeval : PropForm.eval v p
  · simp [hpeval] at hv1
  · simp [hpeval] at hv2

end Problems.compactness
