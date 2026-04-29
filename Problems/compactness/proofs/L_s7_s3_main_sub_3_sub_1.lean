import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s7_s3_main_sub_3_sub_1 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M → p ∈ M := by
  intro α M hFinsat hNeg p q hConj
  by_contra hNotP
  have hNegP : PropForm.neg p ∈ M := (hNeg p).mpr hNotP
  have hSubset : {PropForm.conj p q, PropForm.neg p} ⊆ M := by
    intro x hx
    simp only [Set.mem_insert_iff, Set.mem_singleton_iff] at hx
    rcases hx with rfl | rfl
    · exact hConj
    · exact hNegP
  have hFin : ({PropForm.conj p q, PropForm.neg p} : Set (PropForm α)).Finite :=
    (Set.finite_singleton _).insert _
  obtain ⟨v, hv⟩ := hFinsat _ hSubset hFin
  have h1 := hv (PropForm.conj p q) (by simp)
  have h2 := hv (PropForm.neg p) (by simp)
  simp [PropForm.eval, Bool.and_eq_true] at h1
  simp [PropForm.eval, h1.1] at h2

end Problems.compactness
