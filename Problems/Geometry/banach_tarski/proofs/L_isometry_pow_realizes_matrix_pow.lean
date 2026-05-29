-- Direct ℕ-induction bridging isometry-power to matrix-power (no sub-goals).
-- `induction n generalizing x`; base `simp` (e^0 = id, A^0 = 1). Step: `pow_succ`
-- on both sides, `change` exposes `(e^k * e) x` as `(e^k) (e x)` (defeq), rewrite
-- `he` then the IH, and `Matrix.toLpLin_apply`/`mulVec_mulVec` collapse
-- `toEuclideanLin (A^k) ∘ toEuclideanLin A = toEuclideanLin (A^k * A)`.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11444

namespace Problems.Geometry.banach_tarski

def isometry_pow_realizes_matrix_pow := @Problems.Geometry.banach_tarski.s11444

end Problems.Geometry.banach_tarski
