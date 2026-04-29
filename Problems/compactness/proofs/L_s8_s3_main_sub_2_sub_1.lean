import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s8_s3_main_sub_2_sub_1 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    ∀ p : PropForm α, PropForm.neg p ∈ M → p ∉ M := by
  intro α M hfinsat p hneg hcontra
  have hT : ({p, PropForm.neg p} : Set (PropForm α)) ⊆ M := by
    intro q hq
    simp only [Set.mem_insert_iff, Set.mem_singleton_iff] at hq
    rcases hq with rfl | rfl
    · exact hcontra
    · exact hneg
  have hTfin : ({p, PropForm.neg p} : Set (PropForm α)).Finite :=
    (Set.finite_singleton (PropForm.neg p)).insert p
  obtain ⟨v, hv⟩ := hfinsat _ hT hTfin
  have hp : PropForm.eval v p = true := hv p (by simp)
  have hnegp : PropForm.eval v (PropForm.neg p) = true := hv _ (by simp)
  simp [PropForm.eval, hp] at hnegp

end Problems.compactness
