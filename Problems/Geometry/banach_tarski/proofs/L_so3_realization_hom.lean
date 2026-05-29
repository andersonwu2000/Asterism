-- Realize the two SO(3) generators through an abstract matrix-representation monoid hom.
--   • matrix_rep_monoid_hom: an injective, det-preserving `mat : (E ≃ₗᵢ E) →* Matrix` plus the
--     computation rule `hcomp` reading off the matrix of any isometry acting as `toEuclideanLin M`.
--   • orthogonal_to_linear_isometry_equiv: every orthogonal matrix is the action of some
--     `e : E ≃ₗᵢ[ℝ] E` (the `≃ₗᵢ` analogue of the proved `s11390`).
-- Orthogonality `Mᵀ * M = 1` of the two concrete generators is the cheap √2 computation, inlined.
-- Then g := ![eA, eB]; hcomp turns the actions into `mat (g i) = A/B`, and
-- a_inv_left_inverse/b_inv_left_inverse + `Matrix.inv_eq_left_inv` turn these into the inverse
-- literals. Each sub-goal is strictly simpler: an abstract reusable construction or a pure
-- matrix identity, with no entanglement between the hom and the generators.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11487

namespace Problems.Geometry.banach_tarski

def so3_realization_hom := @Problems.Geometry.banach_tarski.s11487

end Problems.Geometry.banach_tarski
