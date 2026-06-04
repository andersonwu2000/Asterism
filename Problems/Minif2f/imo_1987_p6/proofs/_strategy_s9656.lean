import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs.L_prime_quadratic_step_hard

namespace Problems.Minif2f.imo_1987_p6

-- Case-split on whether `i ≤ ⌊√(p/3)⌋`.
-- • Small case: direct from `hk` (the given primality hypothesis).
-- • Large case: dispatched to `prime_quadratic_step_hard`, which receives
--   the extra premise `⌊√(p/3)⌋ < i` and is strictly simpler than the
--   parent (the trivial half of the case-split is discharged here).
theorem s9656 : ∀ (p : ℕ), Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, (∀ m < i, m ≤ p - 2 → Nat.Prime (m^2 + m + p)) →
    Nat.Prime (i^2 + i + p)  := by
  intro p hp hk i hi ih
  by_cases hsmall : i ≤ Nat.floor (Real.sqrt ((p:ℝ)/3))
  · exact hk i hsmall
  · have hlarge : Nat.floor (Real.sqrt ((p:ℝ)/3)) < i := Nat.lt_of_not_le hsmall
    exact prime_quadratic_step_hard p hp hk i hi hlarge ih

end Problems.Minif2f.imo_1987_p6
