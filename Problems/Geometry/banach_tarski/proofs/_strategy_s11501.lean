import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_bounded_injective_rotation_orbit
import Problems.Geometry.banach_tarski.proofs.L_relaxed_hilbert_hotel

namespace Problems.Geometry.banach_tarski

-- Absorb the single point {0} into closedBall by a Hilbert hotel run along an
-- off-origin rotation whose 0-orbit is injective and stays inside the ball.
-- (1) bounded_injective_rotation_orbit: existence of such ρ (orbit ⊆ ball + pairwise-disjoint).
-- (2) relaxed_hilbert_hotel: the `T ⊆ A` variant of the Hilbert-hotel equidecomposition,
--     dropping the too-strong `∀ x∈A, ρ x∈A` invariance (which fails for off-origin ρ since
--     ρ maps closedBall 0 1 to closedBall (ρ 0) 1).  Instantiate (2) at A = closedBall, D = {0}.
theorem s11501 :
    ∃ e : Equidecomp E (E ≃ᵢ E),
      e.source = Metric.closedBall (0 : E) 1 ∧
      e.target = Metric.closedBall (0 : E) 1 \ {0}  := by
  obtain ⟨ρ, hTA, hdisj⟩ := bounded_injective_rotation_orbit
  exact relaxed_hilbert_hotel (Metric.closedBall (0 : E) 1) ({0} : Set E) ρ
    (by simp) hTA hdisj


end Problems.Geometry.banach_tarski
