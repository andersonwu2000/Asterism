import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s79_sub_1 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    ∀ p : PropForm α, PropForm.neg p ∈ M → p ∉ M := by
  intro α M hfinsat p hneg hp
  have hT : ({p, PropForm.neg p} : Set (PropForm α)) ⊆ M := by
    simp only [Set.insert_subset_iff, Set.singleton_subset_iff]
    exact ⟨hp, hneg⟩
  have hfin : ({p, PropForm.neg p} : Set (PropForm α)).Finite :=
    (Set.finite_singleton (PropForm.neg p)).insert p
  obtain ⟨v, hv⟩ := hfinsat _ hT hfin
  have hvp : PropForm.eval v p = true := hv p (by simp)
  have hvnp : PropForm.eval v (PropForm.neg p) = true :=
    hv (PropForm.neg p) (by simp)
  simp [PropForm.eval, hvp] at hvnp

end Problems.compactness
