import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_no_root_below_sqrt2
import Problems.Minif2f.amc12b_2021_p21.proofs.L_no_root_between_sqrt2_and_three

namespace Problems.Minif2f.amc12b_2021_p21

-- Decompose `x = √2 ∨ 3 < x` for positive roots of `x^(2^√2) = √2^(2^x)` via
-- two non-existence sub-goals on the complementary intervals:
--   (a) the equation has no root in (0, √2);
--   (b) the equation has no root in (√2, 3].
-- Trichotomy on `x` vs `√2` and a case-split on `x ≤ 3` vs `3 < x` then forces
-- `x = √2 ∨ 3 < x`. Each sub-goal is strictly simpler than the parent: it
-- drops the disjunction in the conclusion and adds an extra interval bound on x.
theorem s9708 : ∀ x : ℝ, 0 < x →
    x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x →
    x = Real.sqrt 2 ∨ 3 < x  := by
  intro x hx_pos heq
  have h_no_below := no_root_below_sqrt2
  have h_no_between := no_root_between_sqrt2_and_three
  by_contra h
  rcases lt_trichotomy x (Real.sqrt 2) with hlt | heq2 | hgt
  · exact h_no_below x hx_pos hlt heq
  · exact h (Or.inl heq2)
  · by_cases hle : x ≤ 3
    · exact h_no_between x hx_pos hgt hle heq
    · exact h (Or.inr (lt_of_not_ge hle))

end Problems.Minif2f.amc12b_2021_p21
