import Mathlib
import Problems.Minif2f.aime_1991_p6.Defs
import Problems.Minif2f.aime_1991_p6.proofs.L_bounds_on_r
import Problems.Minif2f.aime_1991_p6.proofs.L_floor_from_bounds

namespace Problems.Minif2f.aime_1991_p6

-- Decomposition: two-way split on the floor-equation pipeline.
-- Step 1 (`bounds_on_r`, Backward): the 73-term floor sum equals 546 pins
--   the fractional part of r into [0.43, 0.44), giving 7.43 ≤ r < 7.44.
-- Step 2 (`floor_from_bounds`, Builder): standard floor characterization
--   ⌊100·r⌋ = 743 ↔ 7.43 ≤ r < 7.44, applied to the bounds from Step 1.
-- Combinator: `floor_from_bounds r (bounds_on_r r h₀)` after `intro r h₀`.
theorem s762 : ∀ (r : ℝ) (h₀ : (∑ k ∈ Finset.Icc (19 : ℕ) 91, Int.floor (r + k / 100)) = 546), Int.floor (100 * r) = 743 := by
  intro r h₀
  have h_bounds := bounds_on_r r h₀
  have h_floor := floor_from_bounds
  exact h_floor r h_bounds

end Problems.Minif2f.aime_1991_p6
