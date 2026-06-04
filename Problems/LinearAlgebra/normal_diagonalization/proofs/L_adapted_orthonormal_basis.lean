-- Witness committed: `e := gramSchmidtOrthonormalBasis hcard b`, where `b` is the
-- Schur-adapted ordinary basis (Library `adapted_basis_exists`).  The ∃ is discharged
-- here; the two sub-goals are about the *fixed* witness, hence strictly smaller:
--   • `flag_span_eq`  — Gram-Schmidt preserves each initial-segment span, so the
--      orthonormal flag `span (e.toBasis '' Iic j)` equals `span (b '' Iic j)`.
--   • `flag_invariant` — the ordinary flag subspace `span (b '' Iic j)` is T-invariant
--      (immediate from the adapted hypothesis `hb`).
-- Linker: rewrite the flag to `b`'s span, apply T-invariance, then `e.toBasis j` lies in
-- its own initial-segment span by `subset_span`.
import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Problems.LinearAlgebra.normal_diagonalization.proofs._strategy_s11544

namespace Problems.LinearAlgebra.normal_diagonalization

def adapted_orthonormal_basis := @Problems.LinearAlgebra.normal_diagonalization.s11544

end Problems.LinearAlgebra.normal_diagonalization
