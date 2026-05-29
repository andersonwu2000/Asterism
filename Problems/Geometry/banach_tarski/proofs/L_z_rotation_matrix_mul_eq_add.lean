-- Direct leaf proof of the z-axis rotation composition law M(θ)·M(φ) = M(θ+φ).
-- Rewrite cos/sin of the sum via the angle-addition formulas, then check the 9
-- matrix entries: `ext` + `fin_cases` reduces to scalar `Fin.sum_univ_three`
-- products closed by `ring`. No sub-goals needed.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11436

namespace Problems.Geometry.banach_tarski

def z_rotation_matrix_mul_eq_add := @Problems.Geometry.banach_tarski.s11436

end Problems.Geometry.banach_tarski
