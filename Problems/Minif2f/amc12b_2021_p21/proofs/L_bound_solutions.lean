-- Contrapositive: if y > 4, then RHS = √2^(2^y) strictly dominates
-- LHS = y^(2^√2) (double-exponential vs polynomial growth), so the
-- equation cannot hold. Single sub-goal isolates the strict bound on
-- (4, ∞); combinator discharges via `ne_of_lt` against `h_eq`.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9706

namespace Problems.Minif2f.amc12b_2021_p21

def bound_solutions := @Problems.Minif2f.amc12b_2021_p21.s9706

end Problems.Minif2f.amc12b_2021_p21
