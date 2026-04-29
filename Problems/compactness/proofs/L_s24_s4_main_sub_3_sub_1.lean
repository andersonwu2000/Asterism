import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s24_s4_main_sub_3_sub_1 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M → p ∈ M := by
  intro α M hFinSat hNeg p q hpq
  by_contra hp
  have hnp : PropForm.neg p ∈ M := (hNeg p).mpr hp
  have hT_sub : ({PropForm.conj p q, PropForm.neg p} : Set (PropForm α)) ⊆ M := by
    simp only [Set.insert_subset_iff, Set.singleton_subset_iff]
    exact ⟨hpq, hnp⟩
  have hT_fin : ({PropForm.conj p q, PropForm.neg p} : Set (PropForm α)).Finite :=
    Set.finite_insert.mpr (Set.finite_singleton _)
  obtain ⟨v, hv⟩ := hFinSat _ hT_sub hT_fin
  have hpq_sat : PropForm.eval v (PropForm.conj p q) = true := by apply hv; simp
  have hnp_sat : PropForm.eval v (PropForm.neg p) = true := by apply hv; simp
  simp only [PropForm.eval] at hpq_sat hnp_sat
  cases h : PropForm.eval v p with
  | false => simp [h] at hpq_sat
  | true  => simp [h] at hnp_sat

end Problems.compactness
