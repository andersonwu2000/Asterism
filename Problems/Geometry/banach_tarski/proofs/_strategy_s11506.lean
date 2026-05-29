import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_cone_is_decomp
import Problems.Geometry.banach_tarski.proofs.L_cone_left_inv
import Problems.Geometry.banach_tarski.proofs.L_cone_map_source
import Problems.Geometry.banach_tarski.proofs.L_cone_map_target
import Problems.Geometry.banach_tarski.proofs.L_cone_right_inv

namespace Problems.Geometry.banach_tarski

-- Cone-lift functor: radially extend the sphere Equidecomp `e` to its cone (0,1]·e.
-- Realizing map  y ↦ ‖y‖ • e (‖y‖⁻¹ • y)  (and its inverse via e.invFun); since e's
-- decomposition isometries fix 0 they commute with radial scaling, so the SAME finite
-- witness set S realizes the cone map. Assemble via Equidecomp.mk ∘ PartialEquiv.mk;
-- source/target are the cone sets definitionally (rfl). The five structure obligations
-- are farmed as standalone sub-goals, each strictly simpler than the existential assembly:
--  • cone_map_source / cone_map_target — radial image lands in the cone of e.target/e.source
--  • cone_left_inv / cone_right_inv     — the radial map and its radial inverse cancel
--  • cone_is_decomp                     — S realizes the cone map (origin-fixing ⇒ equivariant)

theorem s11506 (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S)
    (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∃ e' : Equidecomp E (E ≃ᵢ E),
      e'.source = {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} ∧
      e'.target = {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x}  := by
  refine ⟨Equidecomp.mk (PartialEquiv.mk
      (fun y => ‖y‖ • e.toFun (‖y‖⁻¹ • y))
      (fun y => ‖y‖ • e.invFun (‖y‖⁻¹ • y))
      {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x}
      {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x}
      ?hms ?hmt ?hli ?hri) ⟨S, ?hdec⟩, rfl, rfl⟩
  case hms => exact cone_map_source e S hdec h0 hsrc htgt
  case hmt => exact cone_map_target e S hdec h0 hsrc htgt
  case hli => exact cone_left_inv e S hdec h0 hsrc htgt
  case hri => exact cone_right_inv e S hdec h0 hsrc htgt
  case hdec => exact cone_is_decomp e S hdec h0 hsrc htgt

end Problems.Geometry.banach_tarski
