import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s24_s4_main_sub_3_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, p ∈ M → q ∈ M → PropForm.conj p q ∈ M := by
  intro α M hFinsat hNeg p q hp hq
  by_contra h
  have hNegConj : PropForm.neg (PropForm.conj p q) ∈ M :=
    (hNeg (PropForm.conj p q)).mpr h
  have hSubset : ({PropForm.neg (PropForm.conj p q), p, q} : Set (PropForm α)) ⊆ M := by
    simp only [Set.insert_subset_iff, Set.singleton_subset_iff]
    exact ⟨hNegConj, hp, hq⟩
  have hFin : ({PropForm.neg (PropForm.conj p q), p, q} : Set (PropForm α)).Finite := by
    apply Set.Finite.insert
    apply Set.Finite.insert
    exact Set.finite_singleton _
  obtain ⟨v, hv⟩ := hFinsat _ hSubset hFin
  have h1 := hv (PropForm.neg (PropForm.conj p q)) (by simp)
  have h2 := hv p (by simp)
  have h3 := hv q (by simp)
  simp [PropForm.eval, h2, h3] at h1

end Problems.compactness
