-- Cholesky factorisation via Route 1 (reduce to LDL).
-- Define the Cholesky factor M := LDL.lower hA * diagonal (Real.sqrt ∘ LDL.diagEntries hA).
-- Sub-goals:
--   * `ldl_lower_block_triangular` — the LDL lower factor is block-triangular for
--     the reverse-`Fin` index function (bridge `LDL.lowerInv_triangular` via
--     `blockTriangular_inv_of_blockTriangular`).
--   * `ldl_diag_entries_pos` — diagonal entries are strictly positive over ℝ
--     (derived from `LDL.diag_eq_lowerInv_conj` + the inner-product
--     characterisation in `PosDef`).
--   * `cholesky_factor_eq` — `A = M * Mᵀ` (uses the positivity hypothesis so
--     `√d * √d = d`, then `LDL.lower_conj_diag`).
-- Combinator: multiply `h_BT` with `blockTriangular_diagonal` to get `M`'s
-- block-triangularity, then `Exists.intro` finishes.
import Mathlib
import Problems.LinearAlgebra.cholesky_decomposition.Defs
import Problems.LinearAlgebra.cholesky_decomposition.proofs._strategy_s11060

namespace Problems.LinearAlgebra.cholesky_decomposition

def main := @Problems.LinearAlgebra.cholesky_decomposition.s11060

end Problems.LinearAlgebra.cholesky_decomposition
