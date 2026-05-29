-- Cone-lift functor: radially extend the sphere Equidecomp `e` to its cone (0,1]·e.
-- Realizing map  y ↦ ‖y‖ • e (‖y‖⁻¹ • y)  (and its inverse via e.invFun); since e's
-- decomposition isometries fix 0 they commute with radial scaling, so the SAME finite
-- witness set S realizes the cone map. Assemble via Equidecomp.mk ∘ PartialEquiv.mk;
-- source/target are the cone sets definitionally (rfl). The five structure obligations
-- are farmed as standalone sub-goals, each strictly simpler than the existential assembly:
--  • cone_map_source / cone_map_target — radial image lands in the cone of e.target/e.source
--  • cone_left_inv / cone_right_inv     — the radial map and its radial inverse cancel
--  • cone_is_decomp                     — S realizes the cone map (origin-fixing ⇒ equivariant)
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11506

namespace Problems.Geometry.banach_tarski

def cone_lift_equidecomp := @Problems.Geometry.banach_tarski.s11506

end Problems.Geometry.banach_tarski
