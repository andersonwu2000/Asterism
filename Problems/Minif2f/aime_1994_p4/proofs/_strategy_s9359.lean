import Mathlib
import Problems.Minif2f.aime_1994_p4.Defs
import Problems.Minif2f.aime_1994_p4.proofs.L_sum_at_313_gt_1994
import Problems.Minif2f.aime_1994_p4.proofs.L_sum_mono_ge_313

namespace Problems.Minif2f.aime_1994_p4

-- Trichotomy upper branch: for m > 312 the floor-log sum strictly exceeds 1994.
-- Two sub-goals: (1) a numerical anchor at m = 313 showing the sum is already
-- > 1994 there, and (2) monotonicity of the partial sum in m (each floor term
-- is non-negative for k ≥ 1), so growing m past 313 only adds. `linarith`
-- chains the two.
theorem s9359 : ∀ (m : ℕ), 312 < m →
    (∑ k ∈ Finset.Icc 1 m, Int.floor (Real.logb 2 (k : ℕ))) > 1994  := by
  intro m hm
  have h_at_313 := sum_at_313_gt_1994
  have h_mono := sum_mono_ge_313 m hm
  linarith

end Problems.Minif2f.aime_1994_p4
