import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s8_s3_main_sub_2_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ∃ F : Set (PropForm α), F ⊆ M ∧ F.Finite ∧ ¬Sat (insert p F)) →
    ∀ p : PropForm α, p ∉ M → PropForm.neg p ∈ M := by
  intro α M hfinsat hmax p hp
  by_contra hneg
  obtain ⟨F₁, hF₁sub, hF₁fin, hF₁nsat⟩ := hmax p hp
  obtain ⟨F₂, hF₂sub, hF₂fin, hF₂nsat⟩ := hmax (PropForm.neg p) hneg
  obtain ⟨v, hv⟩ := hfinsat (F₁ ∪ F₂) (Set.union_subset hF₁sub hF₂sub) (hF₁fin.union hF₂fin)
  cases h : PropForm.eval v p
  · apply hF₂nsat
    refine ⟨v, fun q hq => ?_⟩
    rcases Set.mem_insert_iff.mp hq with rfl | hqF₂
    · simp [PropForm.eval, h]
    · exact hv q (Set.mem_union_right F₁ hqF₂)
  · apply hF₁nsat
    refine ⟨v, fun q hq => ?_⟩
    rcases Set.mem_insert_iff.mp hq with rfl | hqF₁
    · exact h
    · exact hv q (Set.mem_union_left F₂ hqF₁)

end Problems.compactness
