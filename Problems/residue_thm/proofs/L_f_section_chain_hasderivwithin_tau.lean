-- Direct chain-rule proof: extract C¹ section `τ' ↦ H τ' t` from joint
-- `ContDiffOn ℝ 2 H` via `.comp` with the constant-t slice map, get its
-- `HasDerivWithinAt` on `Icc 0 1` at τ ∈ Ico 0 1, get `HasDerivAt` of `f`
-- at `H τ t ∈ V` from analyticity, then chain via `comp_hasDerivWithinAt`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10353

namespace Problems.residue_thm

def f_section_chain_hasderivwithin_tau := @Problems.residue_thm.s10353

end Problems.residue_thm
