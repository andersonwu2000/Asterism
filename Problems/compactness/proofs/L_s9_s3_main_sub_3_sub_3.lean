import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s9_s3_main_sub_3_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, p ∈ M → q ∈ M → PropForm.conj p q ∈ M := by
  intro α M hFinsat hNeg p q hp hq
  by_contra h
  have hncpq : PropForm.neg (PropForm.conj p q) ∈ M := (hNeg (PropForm.conj p q)).mpr h
  have hSubset : ({PropForm.neg (PropForm.conj p q), p, q} : Set (PropForm α)) ⊆ M := by
    simp only [Set.insert_subset_iff, Set.singleton_subset_iff]
    exact ⟨hncpq, hp, hq⟩
  have hFin : ({PropForm.neg (PropForm.conj p q), p, q} : Set (PropForm α)).Finite := by
    apply Set.Finite.insert
    apply Set.Finite.insert
    exact Set.finite_singleton q
  obtain ⟨v, hv⟩ := hFinsat _ hSubset hFin
  have hv1 : PropForm.eval v (PropForm.neg (PropForm.conj p q)) = true :=
    hv (PropForm.neg (PropForm.conj p q)) (by simp)
  have hv2 : PropForm.eval v p = true := hv p (by simp)
  have hv3 : PropForm.eval v q = true := hv q (by simp)
  simp [PropForm.eval, hv2, hv3] at hv1

end Problems.compactness
