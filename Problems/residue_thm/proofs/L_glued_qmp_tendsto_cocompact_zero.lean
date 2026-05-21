-- Direct: the if-function agrees with (Q - P) off {a}, which is cocompact-eventually,
-- and (Q - P) → 0 by Tendsto.sub of hQ_decay, hP_decay; close via tendsto_congr'.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10553

namespace Problems.residue_thm

def glued_qmp_tendsto_cocompact_zero := @Problems.residue_thm.s10553

end Problems.residue_thm
