import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs

namespace Problems.Minif2f.imo_1979_p1

-- pointwise_sign_to_diff: parity dispatch via Even.neg_one_pow / Odd.neg_one_pow to
-- rewrite (-1)^(k+1) as ±1, then ring closes the pointwise identity.
theorem pointwise_sign_to_diff : ∀ k : ℕ,
    ((-1 : ℝ) ^ (k + 1) * ((1 : ℝ) / (k : ℝ))) =
      ((1 : ℝ) / (k : ℝ)) - 2 * (if Even k then ((1 : ℝ) / (k : ℝ)) else 0) := by
  intro k
  by_cases he : Even k
  · simp only [he, if_true]
    have h : (-1 : ℝ) ^ (k + 1) = -1 := he.add_one.neg_one_pow
    rw [h]; ring
  · have hodd : Odd k := (Nat.even_or_odd k).resolve_left he
    have h : (-1 : ℝ) ^ (k + 1) = 1 := hodd.add_one.neg_one_pow
    simp only [he, if_false]
    rw [h]; ring

end Problems.Minif2f.imo_1979_p1
