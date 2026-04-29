import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s24_s4_main_sub_3_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M → q ∈ M := by
  intro α M hFinsat hNeg p q hconj
  by_contra hq
  have hNegQ : PropForm.neg q ∈ M := (hNeg q).mpr hq
  have hSubset : ({PropForm.conj p q, PropForm.neg q} : Set (PropForm α)) ⊆ M := by
    simp only [Set.insert_subset_iff, Set.singleton_subset_iff]
    exact ⟨hconj, hNegQ⟩
  have hFin : ({PropForm.conj p q, PropForm.neg q} : Set (PropForm α)).Finite :=
    (Set.finite_singleton _).insert _
  obtain ⟨v, hv⟩ := hFinsat _ hSubset hFin
  have h1 := hv (PropForm.conj p q) (by simp)
  have h2 := hv (PropForm.neg q) (by simp)
  simp only [PropForm.eval, Bool.and_eq_true] at h1
  simp [PropForm.eval, h1.2] at h2

end Problems.compactness
