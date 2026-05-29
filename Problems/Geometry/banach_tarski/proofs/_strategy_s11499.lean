import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_paradoxical_transfer_along_equidecomp
import Problems.Geometry.banach_tarski.proofs.L_ball_origin_absorb_equidecomp

namespace Problems.Geometry.banach_tarski

-- Absorb the origin via a Hilbert-hotel equidecomposition closedBall ≃ closedBall∖{0}
-- (off-origin rotation with injective 0-orbit inside the ball), then transport the
-- punctured-ball paradox (h) up to the full ball via paradoxical_transfer_along_equidecomp.
theorem s11499
    (h : ∃ (f g : Equidecomp E (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.closedBall (0 : E) 1 \ {0} ∧
      f.target = Metric.closedBall (0 : E) 1 \ {0} ∧
      g.target = Metric.closedBall (0 : E) 1 \ {0}) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = Metric.closedBall (0 : E) 1 ∧
      f.target = Metric.closedBall (0 : E) 1 ∧
      g.target = Metric.closedBall (0 : E) 1  := by
  obtain ⟨e, hsrc, htgt⟩ := ball_origin_absorb_equidecomp
  exact paradoxical_transfer_along_equidecomp
    (Metric.closedBall (0 : E) 1) (Metric.closedBall (0 : E) 1 \ {0}) e hsrc htgt h

end Problems.Geometry.banach_tarski
