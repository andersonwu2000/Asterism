import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs.L_alt_eq_full_minus_head
import Problems.Minif2f.imo_1979_p1.proofs.L_tail_eq_full_minus_head

namespace Problems.Minif2f.imo_1979_p1

-- Bridge via full-harmonic minus head: rewrite alternating sum as (sum_all − sum_head_half)
-- and rewrite the tail as (sum_all − sum_head_half); combine by linarith.
theorem s9599 :
    (∑ k ∈ Finset.Icc (1 : ℕ) 1319, (-1 : ℝ) ^ (k + 1) * ((1 : ℝ) / (k : ℝ))) =
      ∑ k ∈ Finset.Icc (660 : ℕ) 1319, ((1 : ℝ) / (k : ℝ))  := by
  have h_alt := alt_eq_full_minus_head
  have h_tail := tail_eq_full_minus_head
  linarith [h_alt, h_tail]
end Problems.Minif2f.imo_1979_p1
