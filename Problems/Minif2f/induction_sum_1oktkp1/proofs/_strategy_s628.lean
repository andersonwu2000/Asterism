import Mathlib
import Problems.Minif2f.induction_sum_1oktkp1.Defs

namespace Problems.Minif2f.induction_sum_1oktkp1

-- Telescoping sum: induct on n. Base n=0 reduces by `simp`; step uses
-- `Finset.sum_range_succ` + ih, then `push_cast`/`field_simp`/`ring`
-- to close `n/(n+1) + 1/((n+1)(n+2)) = (n+1)/(n+2)`.
theorem s628 : ∀ (n : ℕ), (∑ k ∈ Finset.range n, (1 : ℝ) / ((k + 1) * (k + 2))) = n / (n + 1)  := by
  intro n
  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ, ih]
    have h1 : ((n : ℝ) + 1) ≠ 0 := by positivity
    have h2 : ((n : ℝ) + 2) ≠ 0 := by positivity
    push_cast
    field_simp
    ring

end Problems.Minif2f.induction_sum_1oktkp1
