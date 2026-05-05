import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s72_sub_2 : ∀ (D dot L t : ℝ),
    D ≠ 0 →
    0 < L →
    1 / 2 < t →
    t < 1 →
    dot ^ 2 + D ^ 2 ≤ t ^ 2 * L ^ 2 →
    (dot - L) ^ 2 + D ^ 2 ≤ (1 - t) ^ 2 * L ^ 2 →
    False := by
  intro D dot L t hD hL ht1 ht2 h1 h2
  have hD2 : 0 < D ^ 2 := sq_pos_of_ne_zero hD
  -- Adding h1 + h2: (dot - t*L)*(dot - (1-t)*L) + D^2 ≤ 0
  have hprod : (dot - t * L) * (dot - (1 - t) * L) + D ^ 2 ≤ 0 := by nlinarith [mul_pos hL hL]
  -- Negative product + positive factor → other factor negative: (1-t)*L < dot < t*L
  have hdot_gt : (1 - t) * L < dot := by
    by_contra h; push_neg at h
    have hA : 0 ≤ t * L - dot := by nlinarith
    have hB : 0 ≤ (1 - t) * L - dot := by linarith
    nlinarith [mul_nonneg hA hB]
  have hdot_lt : dot < t * L := by
    by_contra h; push_neg at h
    have hA : 0 ≤ dot - t * L := by linarith
    have hB : 0 < dot - (1 - t) * L := by linarith
    nlinarith [mul_nonneg hA (le_of_lt hB)]
  -- L - dot > (1-t)*L, so (L-dot)^2 > (1-t)^2*L^2, contradicting h2 + D^2 > 0
  have h1tL : 0 < (1 - t) * L := mul_pos (by linarith) hL
  have hfac1 : (0 : ℝ) < L - dot - (1 - t) * L := by linarith
  have hfac2 : (0 : ℝ) < L - dot + (1 - t) * L := by linarith
  nlinarith [mul_pos hfac1 hfac2]

end Problems.sylvester_gallai
