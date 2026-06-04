-- Direct leaf: bound y by an integer-arithmetic upper bound, then case-split.
-- From y < x (ℤ) we have x ≥ y+1, so x+y+xy ≥ y²+3y+1; combined with =80
-- this forces y² + 3y ≤ 79, hence y ≤ 7. nlinarith discovers this. Once y is
-- fixed in [1, 7] the equation x + y + xy = 80 is linear in x with 0 < y < x,
-- which omega closes per branch. No sub-goals needed — leaf bypass applies.
import Mathlib
import Problems.Minif2f.amc12a_2015_p10.Defs
import Problems.Minif2f.amc12a_2015_p10.proofs._strategy_s9281

namespace Problems.Minif2f.amc12a_2015_p10

def main := @Problems.Minif2f.amc12a_2015_p10.s9281

end Problems.Minif2f.amc12a_2015_p10
