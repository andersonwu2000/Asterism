import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_ball_paradoxical_of_punctured
import Problems.Geometry.banach_tarski.proofs.L_punctured_ball_paradoxical

namespace Problems.Geometry.banach_tarski

-- Decompose the solid-ball paradox into: (1) the punctured ball closedBall\{0}
-- is paradoxical (radial cone lift of the proved sphere paradox), and
-- (2) single-point (origin) absorption pulls the punctured-ball paradox up to
-- the full closed ball. Glue: feed (1)'s conclusion as (2)'s hypothesis.
theorem s11498 : ∃ (f g : Equidecomp E (E ≃ᵢ E)),
  Disjoint f.source g.source ∧
  f.source ∪ g.source = Metric.closedBall (0 : E) 1 ∧
  f.target = Metric.closedBall (0 : E) 1 ∧
  g.target = Metric.closedBall (0 : E) 1  := by
  have h_punctured := punctured_ball_paradoxical
  exact ball_paradoxical_of_punctured h_punctured

end Problems.Geometry.banach_tarski
