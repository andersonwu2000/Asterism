import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_punctured_ball_of_origin_fixing_sphere
import Problems.Geometry.banach_tarski.proofs.L_sphere_paradoxical_origin_fixing

namespace Problems.Geometry.banach_tarski

-- Cone-lift transport. The punctured closed ball is exactly the radial cone over the unit
-- sphere (cone_over_sphere_eq_punctured_ball / s11488), and an origin-fixing isometry commutes
-- with radial scaling: g (r•x) = r•(g x) (isometry_fixing_origin_smul_comm / s11475). Hence a
-- sphere paradox whose witnessing isometries all fix 0 lifts ray-by-ray (y ↦ ‖y‖•(g (‖y‖⁻¹•y)))
-- to a paradox of closedBall\{0}.
-- (1) sphere_paradoxical_origin_fixing: the proved sphere paradox, strengthened with the extra
--     data that each piece is realized by a finite set of origin-fixing isometries (SO(3)
--     rotations do fix 0). Sphere region only — strictly simpler than the solid-ball assembly.
-- (2) punctured_ball_of_origin_fixing_sphere: takes (1) as a hypothesis and performs the cone
--     lift + reassembly; never re-derives the paradox, so it is a pure transport step.
theorem s11500 : ∃ (f g : Equidecomp E (E ≃ᵢ E)),
    Disjoint f.source g.source ∧
    f.source ∪ g.source = Metric.closedBall (0 : E) 1 \ {0} ∧
    f.target = Metric.closedBall (0 : E) 1 \ {0} ∧
    g.target = Metric.closedBall (0 : E) 1 \ {0}  := by
  exact punctured_ball_of_origin_fixing_sphere sphere_paradoxical_origin_fixing

end Problems.Geometry.banach_tarski
