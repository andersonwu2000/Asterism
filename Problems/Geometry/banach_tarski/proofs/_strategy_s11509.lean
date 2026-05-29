import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_conjugate_origin_orbit
import Problems.Geometry.banach_tarski.proofs.L_exists_small_irrational_rotation

namespace Problems.Geometry.banach_tarski

-- Absorb {0} via an off-origin rotation: ρ conjugates a linear rotation R by a
-- translation that moves the rotation axis off the origin, so the 0-orbit traces a
-- circle of radius ‖c‖ ≤ 1/2 through the origin.
-- (1) exists_small_irrational_rotation: a linear rotation R and a small vector c
--     (‖c‖ ≤ 1/2) such that no positive power of R fixes c (irrational angle).
-- (2) conjugate_origin_orbit: build ρ x = R(x - c) + c; then (ρ^n) 0 = c - R^n c,
--     so ‖(ρ^n) 0‖ ≤ ‖c‖ + ‖R^n c‖ = 2‖c‖ ≤ 1 (in the ball) and (ρ^n) 0 = 0 ↔
--     R^n c = c, excluded for n ≥ 1 by hfix.
theorem s11509 :
    ∃ ρ : E ≃ᵢ E,
      (∀ n : ℕ, (ρ ^ n) 0 ∈ Metric.closedBall (0 : E) 1) ∧
      (∀ n : ℕ, 1 ≤ n → (ρ ^ n) 0 ≠ 0)  := by
  obtain ⟨R, c, hc, hfix⟩ := exists_small_irrational_rotation
  exact conjugate_origin_orbit R c hc hfix

end Problems.Geometry.banach_tarski
