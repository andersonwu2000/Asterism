-- Parametric Leibniz on the circle integral, unfolded to its interval-integral form
-- `∫ θ in 0..(2π), deriv(circleMap) θ • (g(circleMap θ) / (circleMap θ - ζ))`.
-- Neighborhood `s := Metric.ball z δ` with δ = (dist z c - r)/2 stays in the
-- "outside" region {ζ : r < dist ζ c}, ensuring the integrand and its ζ-derivative
-- remain finite. Sub-goals: integrand IntervalIntegrable (1), pointwise HasDerivAt
-- of integrand in ζ (2), and uniform sup-norm bound on the ζ-partial over the ball (3).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10442

namespace Problems.residue_thm

def circle_int_param_diff_outside_at := @Problems.residue_thm.s10442

end Problems.residue_thm
