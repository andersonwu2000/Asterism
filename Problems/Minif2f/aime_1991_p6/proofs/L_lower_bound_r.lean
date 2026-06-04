-- Contrapositive decomposition: assume r < 7.43 and derive sum ≤ 545,
-- contradicting h: sum = 546 via `omega`.
-- Sub-goal `sum_floor_le_545_of_r_lt` (Builder) packages the bound:
--   for k ∈ [19,57] (39 terms) `r+k/100 < 8` so `⌊·⌋ ≤ 7`;
--   for k ∈ [58,91] (34 terms) `r+k/100 < 8.34` so `⌊·⌋ ≤ 8`;
--   total ≤ 39·7 + 34·8 = 545.
import Mathlib
import Problems.Minif2f.aime_1991_p6.Defs
import Problems.Minif2f.aime_1991_p6.proofs._strategy_s9450

namespace Problems.Minif2f.aime_1991_p6

def lower_bound_r := @Problems.Minif2f.aime_1991_p6.s9450

end Problems.Minif2f.aime_1991_p6
