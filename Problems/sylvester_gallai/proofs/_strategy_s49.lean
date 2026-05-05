import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s49_sub_1

namespace Problems.sylvester_gallai

open Classical

theorem s49 : ∀ (P : Finset (ℝ × ℝ)),
    (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
    ((P ×ˢ (P ×ˢ P)).filter (fun t : (ℝ × ℝ) × (ℝ × ℝ) × (ℝ × ℝ) =>
      t.2.1 ≠ t.2.2 ∧ ¬ Collinear t.1 t.2.1 t.2.2)).Nonempty  := by
  intro P hP
  obtain ⟨a, ha, b, hb, c, hc, hnc⟩ := hP
  have hbc : b ≠ c := s49_sub_1 a b c hnc
  refine ⟨(a, b, c), ?_⟩
  simp only [Finset.mem_filter, Finset.mem_product]
  exact ⟨⟨ha, hb, hc⟩, hbc, hnc⟩

end Problems.sylvester_gallai
