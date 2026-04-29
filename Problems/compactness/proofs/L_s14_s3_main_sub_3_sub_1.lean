import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s14_s3_main_sub_3_sub_1 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M → p ∈ M := by
  intro α M hfinsat hneg p q hconj
  by_contra hp
  have hnegp : PropForm.neg p ∈ M := (hneg p).mpr hp
  have hsubset : ({PropForm.conj p q, PropForm.neg p} : Set (PropForm α)) ⊆ M := by
    simp only [Set.insert_subset_iff, Set.singleton_subset_iff]
    exact ⟨hconj, hnegp⟩
  have hfin : ({PropForm.conj p q, PropForm.neg p} : Set (PropForm α)).Finite :=
    Set.finite_insert.mpr (Set.finite_singleton _)
  obtain ⟨v, hv⟩ := hfinsat _ hsubset hfin
  have hcpq : PropForm.eval v (PropForm.conj p q) = true := by apply hv; simp
  have hnpv : PropForm.eval v (PropForm.neg p) = true := by apply hv; simp
  simp only [PropForm.eval] at hcpq hnpv
  cases h : PropForm.eval v p with
  | false => simp [h] at hcpq
  | true  => simp [h] at hnpv

end Problems.compactness
