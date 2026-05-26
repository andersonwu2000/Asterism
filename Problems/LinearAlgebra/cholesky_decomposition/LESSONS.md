<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Over ℝ, `simp only [Matrix.conjTranspose, Matrix.transpose]` unfolds `Mᴴ` and `Mᵀ` to the same `fun i j => M j i` expression (star is identity on ℝ), letting you directly apply `ᴴ`-stated LDL lemmas (e.g. `LDL.lower_conj_diag`) when the goal uses `ᵀ`.
- For `(M * A * Mᴴ).PosDef` from `A.PosDef` + invertible `M`, use `Matrix.PosDef.mul_mul_conjTranspose_same` fed by `Matrix.vecMul_injective_of_invertible M`; then `Matrix.posDef_diagonal_iff` peels a PosDef `Matrix.diagonal d` into `∀ i, 0 < d i` (and `LDL.diag hA = Matrix.diagonal (LDL.diagEntries hA)` holds by `rfl`).
- `Matrix.blockTriangular_inv_of_blockTriangular` needs `Invertible (LDL.lowerInv hA)` in scope (use `LDL.invertibleLowerInv hA`) and the hypothesis introduced from `BlockTriangular` carries an un-beta-reduced lambda — `simp only at hij` before `omega` to expose `(n-1) - j.val < (n-1) - i.val`.
