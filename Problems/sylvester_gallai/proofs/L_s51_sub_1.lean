import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s51_sub_1 : ∀ (a b c : ℝ × ℝ),
    a ≠ b →
    Collinear a b c →
    ∃ t : ℝ, c.1 = a.1 + t * (b.1 - a.1) ∧ c.2 = a.2 + t * (b.2 - a.2) := by
  intro a b c hab hcol
  simp only [Collinear] at hcol
  -- hcol : (a.1 - c.1) * (b.2 - c.2) = (a.2 - c.2) * (b.1 - c.1)
  -- Ring-equivalent: (c.1 - a.1) * (b.2 - a.2) = (c.2 - a.2) * (b.1 - a.1)
  have hcol2 : (c.1 - a.1) * (b.2 - a.2) = (c.2 - a.2) * (b.1 - a.1) := by
    linear_combination -hcol
  -- Since a ≠ b, at least one coordinate differs
  have hne : a.1 ≠ b.1 ∨ a.2 ≠ b.2 := by
    by_contra hc
    push_neg at hc
    exact hab (Prod.ext hc.1 hc.2)
  by_cases h1 : b.1 = a.1
  · -- b.1 = a.1, so b.2 ≠ a.2; use t = (c.2 - a.2) / (b.2 - a.2)
    have h2 : a.2 ≠ b.2 := hne.resolve_left (not_ne_iff.mpr h1.symm)
    have hne2 : b.2 - a.2 ≠ 0 := sub_ne_zero.mpr (Ne.symm h2)
    -- With b.1 = a.1, hcol2 becomes (c.1 - a.1) * (b.2 - a.2) = 0, so c.1 = a.1
    have hba1 : b.1 - a.1 = 0 := sub_eq_zero.mpr h1
    have hc1 : c.1 = a.1 := by
      have key : (c.1 - a.1) * (b.2 - a.2) = 0 := by
        rw [hcol2, hba1, mul_zero]
      rcases mul_eq_zero.mp key with h | h
      · linarith
      · exact absurd h hne2
    use (c.2 - a.2) / (b.2 - a.2)
    refine ⟨?_, ?_⟩
    · rw [hc1, hba1, mul_zero, add_zero]
    · have : (c.2 - a.2) / (b.2 - a.2) * (b.2 - a.2) = c.2 - a.2 :=
        div_mul_cancel₀ (c.2 - a.2) hne2
      linarith
  · -- b.1 ≠ a.1; use t = (c.1 - a.1) / (b.1 - a.1)
    have hne1 : b.1 - a.1 ≠ 0 := sub_ne_zero.mpr h1
    use (c.1 - a.1) / (b.1 - a.1)
    refine ⟨?_, ?_⟩
    · have : (c.1 - a.1) / (b.1 - a.1) * (b.1 - a.1) = c.1 - a.1 :=
        div_mul_cancel₀ (c.1 - a.1) hne1
      linarith
    · have key : (c.1 - a.1) / (b.1 - a.1) * (b.2 - a.2) = c.2 - a.2 := by
        rw [div_mul_eq_mul_div, div_eq_iff hne1]
        linear_combination hcol2
      linarith

end Problems.sylvester_gallai
