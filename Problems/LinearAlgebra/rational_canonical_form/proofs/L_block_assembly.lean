-- Transport-only assembly: conjugate `T` through the K-linear equiv
--   `g = (AEval'.of T) ≫ (e.restrictScalars K) : V ≃ₗ[K] ⨁ᵢ K[X]/(fᵢ)`,
-- and read off the block-diagonal matrix in the transported power basis `c`.
-- `intertwine_x` : `g` carries `T` to the `K[X]`-scalar action `X • ·` (= `S`)
--   (via `AEval'.X_smul_of` + `e`'s `K[X]`-linearity) — no matrices.
-- `conj_matrix`  : abstract conjugation lemma — `toMatrix (c.map g.symm) _ T = toMatrix c c S`.
-- `block_diag`   : the `X`-action on the direct sum is `blockDiagonal'` of the per-block
--   `mulLeft K (root fᵢ)` matrices (the internal-direct-sum / DFinsupp.basis computation).
-- Combine by `rw [hconj, hblock]`. Each piece drops either `T`/`e` (block_diag) or the
--   rational-canonical-form specifics (conj_matrix), so all three are strictly simpler.
import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs._strategy_s11593

namespace Problems.LinearAlgebra.rational_canonical_form

def block_assembly := @Problems.LinearAlgebra.rational_canonical_form.s11593

end Problems.LinearAlgebra.rational_canonical_form
