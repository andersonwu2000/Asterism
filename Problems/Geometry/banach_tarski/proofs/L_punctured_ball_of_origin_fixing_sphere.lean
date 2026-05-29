-- Cone-lift transport: lift each sphere Equidecomp piece radially to the punctured ball.
-- Each piece's decomposition isometries fix 0, hence commute with radial scaling, so the
-- map y ↦ ‖y‖•(piece(‖y‖⁻¹•y)) extends each piece to the cone of its source. The cone of
-- the unit sphere is the punctured ball (cone_over_sphere_eq_punctured_ball / s11488), so
-- coning the two sphere pieces reassembles the punctured-ball paradox.
-- (1) cone_lift_equidecomp: the abstract single-piece cone functor (origin-fixing ⇒ radial).
-- (2) cone_distrib_union / (3) cone_preserves_disjoint: set-algebra of the cone over a sphere.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11502

namespace Problems.Geometry.banach_tarski

def punctured_ball_of_origin_fixing_sphere := @Problems.Geometry.banach_tarski.s11502

end Problems.Geometry.banach_tarski
