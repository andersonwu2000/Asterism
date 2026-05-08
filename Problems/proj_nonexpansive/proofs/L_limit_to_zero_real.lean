import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- limit_to_zero_real: real-line limit lemma — if `0 ≤ a + t·b` for every
-- `t ∈ (0,1]` then `0 ≤ a`. Proof: by contradiction assume `a < 0`; choose
-- `t = 1` if `b ≤ 0` (then `a + b ≤ a < 0`), else `t = min 1 (-a/(2b))`
-- (then `t·b ≤ -a/2`, so `a + t·b ≤ a/2 < 0`); contradicts the hypothesis.
theorem limit_to_zero_real :
    ∀ a b : ℝ, (∀ t : ℝ, 0 < t → t ≤ 1 → 0 ≤ a + t * b) → 0 ≤ a := by
  intro a b h
  by_contra hla
  have hla : a < 0 := lt_of_not_ge hla
  have key : ∃ t : ℝ, 0 < t ∧ t ≤ 1 ∧ a + t * b < 0 := by
    rcases le_or_gt b 0 with hb | hb
    · refine ⟨1, one_pos, le_refl _, ?_⟩
      nlinarith
    · refine ⟨min 1 (-a / (2 * b)), ?_, min_le_left _ _, ?_⟩
      · refine lt_min one_pos ?_
        apply div_pos
        · linarith
        · linarith
      · have hmin : min 1 (-a / (2 * b)) ≤ -a / (2 * b) := min_le_right _ _
        have hb2 : (0:ℝ) < 2 * b := by linarith
        have : min 1 (-a / (2 * b)) * b ≤ -a / 2 := by
          have h1 : -a / (2 * b) * b = -a / 2 := by field_simp
          calc min 1 (-a / (2 * b)) * b
              ≤ -a / (2 * b) * b := mul_le_mul_of_nonneg_right hmin hb.le
            _ = -a / 2 := h1
        linarith
  obtain ⟨t, ht1, ht2, ht3⟩ := key
  linarith [h t ht1 ht2]

end Problems.proj_nonexpansive
