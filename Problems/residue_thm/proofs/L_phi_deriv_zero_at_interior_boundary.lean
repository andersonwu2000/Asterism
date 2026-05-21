-- Case split on `hbnd : φ t = 0 ∨ φ t = 1`.
-- Each case is the Fermat-extremum argument at an interior point of `Icc 0 1`:
-- if φ t hits the lower (resp. upper) end of the range, t is an interior local
-- min (resp. max), so `deriv φ t = 0` by `IsLocalMin/Max.deriv_eq_zero`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10647

namespace Problems.residue_thm

def phi_deriv_zero_at_interior_boundary := @Problems.residue_thm.s10647

end Problems.residue_thm
