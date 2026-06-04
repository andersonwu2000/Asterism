-- Decomposition: two-way split on the floor-equation pipeline.
-- Step 1 (`bounds_on_r`, Backward): the 73-term floor sum equals 546 pins
--   the fractional part of r into [0.43, 0.44), giving 7.43 ≤ r < 7.44.
-- Step 2 (`floor_from_bounds`, Builder): standard floor characterization
--   ⌊100·r⌋ = 743 ↔ 7.43 ≤ r < 7.44, applied to the bounds from Step 1.
-- Combinator: `floor_from_bounds r (bounds_on_r r h₀)` after `intro r h₀`.
import Mathlib
import Problems.Minif2f.aime_1991_p6.Defs
import Problems.Minif2f.aime_1991_p6.proofs._strategy_s762

namespace Problems.Minif2f.aime_1991_p6

def main := @Problems.Minif2f.aime_1991_p6.s762

end Problems.Minif2f.aime_1991_p6
