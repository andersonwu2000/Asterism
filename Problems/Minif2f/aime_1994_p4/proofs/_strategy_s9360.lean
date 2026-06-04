import Mathlib
import Problems.Minif2f.aime_1994_p4.Defs
import Problems.Minif2f.aime_1994_p4.proofs.L_bound_311
import Problems.Minif2f.aime_1994_p4.proofs.L_sum_mono_311

namespace Problems.Minif2f.aime_1994_p4

-- Two-step bound: monotonicity of the partial sum lifts m ≤ 311 to a
-- comparison with the partial sum at 311; a closed-form numeric bound
-- caps the m = 311 sum at 1993; linarith composes the two with the
-- strict < 1994 conclusion.
theorem s9360 : ∀ (m : ℕ), 0 < m → m < 312 →
    (∑ k ∈ Finset.Icc 1 m, Int.floor (Real.logb 2 (k : ℕ))) < 1994  := by
  intro m hm hm312
  have h_mono := sum_mono_311 m hm hm312
  have h_bound := bound_311 m hm hm312
  linarith
end Problems.Minif2f.aime_1994_p4
