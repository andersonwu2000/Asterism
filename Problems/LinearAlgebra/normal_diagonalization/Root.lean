-- Spectral theorem for normal operators, via the Schur ⇒ spectral route.
-- Decomposition (3 sub-goals + an `obtain`/`exact` combinator):
--   * `block_triangular_basis` — Schur (Library) + Gram-Schmidt give an orthonormal
--     basis `e` in which `T` is (block-)upper-triangular.
--   * `commute_bridge` — normality `Commute (adjoint T) T` transports through the
--     star-algebra equiv to `Commute Mᴴ M` for `M = toMatrix e e T`.
--   * `matrix_core` — pure matrix crux: upper-triangular + normal ⇒ diagonal.
-- They combine: triangularize, then feed triangularity + matrix-normality into the
-- matrix lemma to get `IsDiag`. Each piece is strictly smaller — one basis existence,
-- one star-algebra bridge, one matrix induction.
import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Problems.LinearAlgebra.normal_diagonalization.proofs._strategy_s11530

namespace Problems.LinearAlgebra.normal_diagonalization

def main := @Problems.LinearAlgebra.normal_diagonalization.s11530

end Problems.LinearAlgebra.normal_diagonalization
