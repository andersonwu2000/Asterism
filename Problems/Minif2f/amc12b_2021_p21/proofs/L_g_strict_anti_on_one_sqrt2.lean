-- Decompose `StrictAntiOn g (Icc 1 √2)` via `strictAntiOn_of_deriv_neg` on the convex set
-- `Icc 1 √2 = convex_Icc 1 √2`. The two side-conditions are strictly simpler analytic facts:
-- `h_cont` — `ContinuousOn g (Icc 1 √2)` (a `ContinuousOn.sub` of an rpow times a constant
-- and a constant times a `log`); and `h_deriv` — pointwise negativity of `deriv g` on
-- `interior (Icc 1 √2) = Ioo 1 √2` (one-variable analytic inequality where the `−2^√2/t`
-- term dominates the small `2^t · log 2 · log √2` term throughout the interval).  Each is
-- one structural step below the parent monotonicity statement.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9818

namespace Problems.Minif2f.amc12b_2021_p21

def g_strict_anti_on_one_sqrt2 := @Problems.Minif2f.amc12b_2021_p21.s9818

end Problems.Minif2f.amc12b_2021_p21
