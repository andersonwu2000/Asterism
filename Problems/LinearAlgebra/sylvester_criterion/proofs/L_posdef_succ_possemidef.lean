-- Schur-complement induction step: M (size n+1) is PosSemidef. Reindex via
-- `finSumFinEquiv` into 2×2 blocks, then `PosDef.fromBlocks₁₁` reduces PosSemidef
-- of the whole to PosSemidef of the Schur complement. Three strictly-simpler pieces:
--   • leading_block_posdef     — the top-left n×n block is PosDef (uses `ih`);
--   • block_conjtranspose      — Hermitian symmetry of the off-diagonal blocks;
--   • schur_complement_possemidef — the 1-dim Schur complement is PosSemidef.
import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs._strategy_s11605

namespace Problems.LinearAlgebra.sylvester_criterion

def posdef_succ_possemidef := @Problems.LinearAlgebra.sylvester_criterion.s11605

end Problems.LinearAlgebra.sylvester_criterion
