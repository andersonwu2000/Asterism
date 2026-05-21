-- Decomposition: replace the a.e.-on-uIoc claim with the pointwise chain rule
-- on the open interval Ioo 0 1 (full measure in uIoc 0 1).  The pointwise
-- sub-goal absorbs the technical boundary handling (φ t may hit Icc-endpoints,
-- where γ is only differentiable within Icc); the patch then upgrades the
-- pointwise equality to an a.e. equality on the closed half-open interval.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10624

namespace Problems.residue_thm

def chain_rule_compose_reparam_ae := @Problems.residue_thm.s10624

end Problems.residue_thm
