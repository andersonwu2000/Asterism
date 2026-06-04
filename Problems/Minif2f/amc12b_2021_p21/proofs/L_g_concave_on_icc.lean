-- Concave − convex = concave: split g(z) = 2^√2·log z − 2^z·log √2.
-- Sub-goal 1: concavity of the log term (positive scalar × log, log strictly concave).
-- Sub-goal 2: convexity of the exponential term (positive scalar × 2^z, 2^z convex).
-- Combine via ConcaveOn.sub.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9822

namespace Problems.Minif2f.amc12b_2021_p21

def g_concave_on_icc := @Problems.Minif2f.amc12b_2021_p21.s9822

end Problems.Minif2f.amc12b_2021_p21
