-- Decompose `StrictAntiOn f (Ioi 3)` via `strictAntiOn_of_deriv_neg` on the convex set
-- `Ioi 3 = convex_Ioi 3`. The two side-conditions are strictly simpler analytic facts:
-- h_cont — `ContinuousOn f (Ioi 3)` (a `ContinuousOn.sub` of two rpow factors); and
-- h_deriv — pointwise negativity of `deriv f` on `interior (Ioi 3) = Ioi 3` (single-variable
-- analytic inequality).  Each is one step below the parent monotonicity statement.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9751

namespace Problems.Minif2f.amc12b_2021_p21

def func_strict_anti_on_three := @Problems.Minif2f.amc12b_2021_p21.s9751

end Problems.Minif2f.amc12b_2021_p21
