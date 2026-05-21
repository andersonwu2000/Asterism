-- Direct proof: pointwise rewrite a*(2*b) = 2 • (a*b), pull const out via integral_smul,
-- then apply intervalIntegral.smul_integral_comp_mul_sub with (a:=1/2,b:=1,c:=2,d:=1).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10681

namespace Problems.residue_thm

def subst_linear_2t_minus_1 := @Problems.residue_thm.s10681

end Problems.residue_thm
