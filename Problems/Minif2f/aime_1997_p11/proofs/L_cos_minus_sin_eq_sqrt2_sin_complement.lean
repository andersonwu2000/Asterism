import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

-- entry_kind: Builder
-- cos_minus_sin_eq_sqrt2_sin_complement: Real.sin_sub + sin/cos_pi_div_four give √2·(√2/2)=1,
-- which closes cos x - sin x = √2·sin(π/4 - x) via explicit factor witness and linarith.
set_option linter.style.longLine false in
open Real in
theorem cos_minus_sin_eq_sqrt2_sin_complement : ∀ (n : ℕ),
    Real.cos ((n : ℝ) * π / 180) - Real.sin ((n : ℝ) * π / 180) =
    Real.sqrt 2 * Real.sin (((45 : ℝ) - n) * π / 180) := by
  intro n
  have heq : ((45 : ℝ) - ↑n) * π / 180 = π / 4 - ↑n * π / 180 := by ring
  rw [heq, Real.sin_sub, Real.sin_pi_div_four, Real.cos_pi_div_four]
  have h1 : Real.sqrt 2 * (Real.sqrt 2 / 2) = 1 := by
    have := Real.mul_self_sqrt (show (0:ℝ) ≤ 2 by norm_num); linarith
  have h2 : Real.sqrt 2 * (Real.sqrt 2 / 2 * Real.cos (↑n * π / 180)) =
      Real.cos (↑n * π / 180) := by
    calc Real.sqrt 2 * (Real.sqrt 2 / 2 * Real.cos (↑n * π / 180))
        = Real.sqrt 2 * (Real.sqrt 2 / 2) * Real.cos (↑n * π / 180) := by ring
      _ = Real.cos (↑n * π / 180) := by rw [h1]; ring
  have h3 : Real.sqrt 2 * (Real.sqrt 2 / 2 * Real.sin (↑n * π / 180)) =
      Real.sin (↑n * π / 180) := by
    calc Real.sqrt 2 * (Real.sqrt 2 / 2 * Real.sin (↑n * π / 180))
        = Real.sqrt 2 * (Real.sqrt 2 / 2) * Real.sin (↑n * π / 180) := by ring
      _ = Real.sin (↑n * π / 180) := by rw [h1]; ring
  linarith [mul_sub (Real.sqrt 2) (Real.sqrt 2 / 2 * Real.cos (↑n * π / 180))
              (Real.sqrt 2 / 2 * Real.sin (↑n * π / 180)), h2, h3]

end Problems.Minif2f.aime_1997_p11
