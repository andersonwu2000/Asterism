import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s5_s3_main_sub_2_sub_1 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, PropForm.neg p ∈ M → p ∉ M := by
  intro α M hfinsat _hmax p hneg hp
  have hsubset : ({p, PropForm.neg p} : Set (PropForm α)) ⊆ M := by
    simp only [Set.insert_subset_iff, Set.singleton_subset_iff]
    exact ⟨hp, hneg⟩
  have hfin : ({p, PropForm.neg p} : Set (PropForm α)).Finite :=
    Set.finite_insert.mpr (Set.finite_singleton _)
  obtain ⟨v, hv⟩ := hfinsat _ hsubset hfin
  have hpv : PropForm.eval v p = true := by apply hv; simp
  have hnpv : PropForm.eval v (PropForm.neg p) = true := by apply hv; simp
  simp only [PropForm.eval] at hnpv
  simp [hpv] at hnpv

end Problems.compactness
