-- Split the LHS integral at `t = 1/2` (additivity), then identify each half
-- with the corresponding α'/β' integral via the inverse substitution
-- `u = 2t` (resp. `u = 2t - 1`) which sends γ to α' (resp. β').
-- Sub-goals: integrability/additivity at the midpoint and the two half-integral
-- substitutions are each smaller than the full statement; the closer is `rw`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10662

namespace Problems.residue_thm

def flat_concat_ftc_integral_split := @Problems.residue_thm.s10662

end Problems.residue_thm
