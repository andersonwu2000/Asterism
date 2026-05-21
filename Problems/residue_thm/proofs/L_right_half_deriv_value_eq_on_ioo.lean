-- For t ∈ Ioo (1/2) 1, the piecewise integral function F(t) is eventually equal
-- (on a neighborhood of t) to the split form G(t) = α'(0) + ∫₀^(1/2) (left branch) +
-- ∫_(1/2)^t (right branch), whose derivative at t is 2·derivWithin β' (Icc 0 1) (2t-1)
-- by FTC. Combine via HasDerivAt.congr_of_eventuallyEq and .deriv.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10680

namespace Problems.residue_thm

def right_half_deriv_value_eq_on_ioo := @Problems.residue_thm.s10680

end Problems.residue_thm
