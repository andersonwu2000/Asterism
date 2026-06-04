-- Triangle-inequality split of the sum ∑_{k=1}^{119} |kx - 1| at k = 84/85.
-- Sub-goals: (1) a Finset split identity at 84, (2) lower-half bound
--   ∑_{k=1}^{84} |kx-1| ≥ 84 - 3570x  (by |·| ≥ -·, and ∑_{k=1}^{84} k = 3570),
-- (3) upper-half bound ∑_{k=85}^{119} |kx-1| ≥ 3570x - 35
--   (by |·| ≥ ·, and ∑_{k=85}^{119} k = 3570 with 35 terms).
-- Summing gives (84 - 3570x) + (3570x - 35) = 49, closed by `rw [h_split]; linarith`.
import Mathlib
import Problems.Minif2f.amc12a_2010_p22.Defs
import Problems.Minif2f.amc12a_2010_p22.proofs._strategy_s9354

namespace Problems.Minif2f.amc12a_2010_p22

def main := @Problems.Minif2f.amc12a_2010_p22.s9354

end Problems.Minif2f.amc12a_2010_p22
