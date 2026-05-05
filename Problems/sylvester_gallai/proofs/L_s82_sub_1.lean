import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
open Classical in
theorem s82_sub_1 (P : Finset (ℝ × ℝ))
    (h_noncol : ∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c)
    (h_skolem : ∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q)
    (h_witness : ∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r) :
    ((P ×ˢ P ×ˢ P).filter
        (fun t : (ℝ × ℝ) × (ℝ × ℝ) × (ℝ × ℝ) =>
          t.1 ≠ t.2.1 ∧ ¬ Collinear t.1 t.2.1 t.2.2)).Nonempty := by
  obtain ⟨p, hp, q, hq, r, hr, hpq, hncol⟩ := h_witness
  refine ⟨(p, q, r), ?_⟩
  simp only [Finset.mem_filter, Finset.mem_product]
  exact ⟨⟨hp, hq, hr⟩, hpq, hncol⟩

end Problems.sylvester_gallai
