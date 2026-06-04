-- Split the parent bound by m % 4, mirroring s9655's residue-class decomposition
-- for the real part. Each sub-goal fixes a single residue mod 4 — strictly
-- simpler than the parent (one residue class instead of all four).
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9687

namespace Problems.Minif2f.amc12a_2009_p15

def sum_im_le_48_below_97 := @Problems.Minif2f.amc12a_2009_p15.s9687

end Problems.Minif2f.amc12a_2009_p15
