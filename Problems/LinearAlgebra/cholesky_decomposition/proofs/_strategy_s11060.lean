import Mathlib
import Problems.LinearAlgebra.cholesky_decomposition.Defs
import Problems.LinearAlgebra.cholesky_decomposition.proofs.L_cholesky_factor_eq
import Problems.LinearAlgebra.cholesky_decomposition.proofs.L_ldl_diag_entries_pos
import Problems.LinearAlgebra.cholesky_decomposition.proofs.L_ldl_lower_block_triangular

namespace Problems.LinearAlgebra.cholesky_decomposition

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
theorem s11060 : ∀ {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ),
  A.PosDef →
  ∃ L : Matrix (Fin n) (Fin n) ℝ,
    L.BlockTriangular (fun i => (n - 1 : ℕ) - (i : ℕ)) ∧
    A = L * Matrix.transpose L  := by
  intro n A hA
  have h_BT : (LDL.lower hA).BlockTriangular (fun i : Fin n => (n - 1 : ℕ) - (i : ℕ)) :=
    ldl_lower_block_triangular hA
  have h_pos : ∀ i, 0 < LDL.diagEntries hA i := ldl_diag_entries_pos hA
  have h_eq : A =
    (LDL.lower hA * Matrix.diagonal (fun i => Real.sqrt (LDL.diagEntries hA i))) *
    (LDL.lower hA * Matrix.diagonal (fun i => Real.sqrt (LDL.diagEntries hA i))).transpose :=
    cholesky_factor_eq hA h_pos
  refine ⟨_, ?_, h_eq⟩
  exact h_BT.mul (Matrix.blockTriangular_diagonal _)

end Problems.LinearAlgebra.cholesky_decomposition
