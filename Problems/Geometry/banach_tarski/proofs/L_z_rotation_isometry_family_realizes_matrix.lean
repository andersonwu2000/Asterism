-- Construct the z-rotation isometry family by realizing each orthogonal block matrix.
-- `hreal`: each M θ is orthogonal (z_rotation_block_orthogonal) so PROVED
-- orthogonal_matrix_isometry_equiv gives an `e : E ≃ᵢ E` acting as `toEuclideanLin (M θ)`;
-- `choose` extracts the family R. Origin clause: linear maps fix 0 (`simp`). Realization
-- clause (3) is `hR` verbatim. Power law: IsometryEquiv `ext`, then
-- `isometry_pow_realizes_matrix_pow` reduces `(R θ)^n x` to `toEuclideanLin (M θ ^ n) x`,
-- and `z_rotation_matrix_pow` collapses `M θ ^ n = M (n·θ)`. Three sub-goals: the matrix
-- power law (pure matrix induction), the isometry-power/matrix-power bridge (group induction),
-- and per-θ orthogonality of the block (pure entry computation).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11442

namespace Problems.Geometry.banach_tarski

def z_rotation_isometry_family_realizes_matrix := @Problems.Geometry.banach_tarski.s11442

end Problems.Geometry.banach_tarski
