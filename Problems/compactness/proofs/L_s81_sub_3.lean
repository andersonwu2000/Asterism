import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s81_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, p ∈ M → q ∈ M → PropForm.conj p q ∈ M := by
  intro α M hMfinsat hneg p q hp hq
  by_contra h
  have hnc : PropForm.neg (PropForm.conj p q) ∈ M := (hneg (PropForm.conj p q)).mpr h
  have hTsub : ({p, q, PropForm.neg (PropForm.conj p q)} : Set (PropForm α)) ⊆ M := by
    intro x hx
    simp only [Set.mem_insert_iff, Set.mem_singleton_iff] at hx
    rcases hx with rfl | rfl | rfl
    · exact hp
    · exact hq
    · exact hnc
  have hTfin : ({p, q, PropForm.neg (PropForm.conj p q)} : Set (PropForm α)).Finite := by
    apply Set.Finite.insert
    apply Set.Finite.insert
    exact Set.finite_singleton _
  obtain ⟨v, hv⟩ := hMfinsat _ hTsub hTfin
  have hvp : PropForm.eval v p = true := hv p (by simp)
  have hvq : PropForm.eval v q = true := hv q (by simp)
  have hvnc : PropForm.eval v (PropForm.neg (PropForm.conj p q)) = true :=
    hv _ (by simp)
  simp [PropForm.eval, hvp, hvq] at hvnc

end Problems.compactness
