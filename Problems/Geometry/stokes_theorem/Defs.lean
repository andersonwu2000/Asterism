/-
  Defs.lean — assembles the final inputs to the generalized Stokes theorem from the
  tower's Library:
    * `pullbackBdry` (= `ι*`): P10's `pullbackBdryFun` + its smoothness witness
      `Problems.Geometry.stokes_pullback.main`, as a genuine smooth `n`-form on `∂M`.
    * `instBdryOriented`: `∂M`'s `OrientedManifold` instance — `refForm` is P12b's
      `inducedOrient` (`ι_ν μ`), `refForm_ne` its nowhere-vanishing `Problems.Geometry.stokes_bdry_oriented.main`.
  The Root proves `∫_M dφ = ∫_∂M ι*φ`. Cites P4/P6/P10/P11/P12/P12b.
-/
import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_chart_target_eq_face_embed_preimage
import Problems.Geometry.stokes_bdry_compact.Defs
import Problems.Geometry.stokes_bdry_invfun_mem.Defs
import Problems.Geometry.stokes_bdry_invfun_mem.proofs.L_symm_mem_boundary_of_frontier
import Problems.Geometry.stokes_bdry_manifold.Defs
import Problems.Geometry.stokes_bdry_manifold.Root
import Problems.Geometry.stokes_bdry_oriented.Defs
import Problems.Geometry.stokes_bdry_oriented.Root
import Problems.Geometry.stokes_bdry_oriented.proofs.L_chartfun_pos_ray
import Problems.Geometry.stokes_bdry_oriented.proofs.L_curry_face_apply_basis
import Problems.Geometry.stokes_bdry_oriented.proofs.L_face_embed_basis
import Problems.Geometry.stokes_bdry_oriented.proofs.L_pou_ne_zero_mem_chart_source
import Problems.Geometry.stokes_dd_zero.Defs
import Problems.Geometry.stokes_dd_zero.proofs.L_form_in_coord_mext_deriv_eq
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_form_coord_comp.Defs
import Problems.Geometry.stokes_form_coord_comp.Root
import Problems.Geometry.stokes_form_coord_self.Root
import Problems.Geometry.stokes_induced_orient.Defs
import Problems.Geometry.stokes_induced_orient.proofs.L_chartfun_triv_read
import Problems.Geometry.stokes_integral.Defs
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_differentiable_within_range
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_eq_coord_change
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_pullback
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_smooth
import Problems.Geometry.stokes_pullback.Defs
import Problems.Geometry.stokes_pullback.Root
import Problems.Geometry.stokes_pullback.proofs.L_bdry_val_contmdiff
import Problems.Geometry.stokes_pullback.proofs.L_bdry_val_rep_eq_faceembed
import Problems.Geometry.stokes_pullback.proofs.L_extchart_val_eq_faceembed_chartat
import Problems.Geometry.stokes_pullback.proofs.L_face_embed_eq_clm_apply
import Problems.Geometry.stokes_pullback.proofs.L_pullback_triv_read

open scoped Manifold Bundle ContDiff
open Bundle
open Problems.Geometry.stokes_form_bundle (DiffForm)
open Problems.Geometry.stokes_integral (OrientedManifold)
open Problems.Geometry.stokes_pullback (pullbackBdryFun)
open Problems.Geometry.stokes_bdry_oriented (inducedOrient)
open Problems.Geometry.stokes_bdry_compact (Bdry)

namespace Problems.Geometry.stokes_theorem

variable {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
  [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
  [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]

/-- The pullback `ι* φ` of a boundary `n`-form along `ι : ∂M ↪ M`, as a genuine smooth
    `n`-form on `∂M`: P10's `pullbackBdryFun` with smoothness `Problems.Geometry.stokes_pullback.main`. -/
noncomputable def pullbackBdry (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    DiffForm (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (Bdry n M) n where
  toFun := pullbackBdryFun φ
  contMDiff_toFun := Problems.Geometry.stokes_pullback.main φ

/-- `M`'s orientation induces one on `∂M`: the `OrientedManifold` instance the boundary
    integral `∫_∂M` reads. `refForm` is P12b's `inducedOrient` (`ι_ν μ`); `refForm_ne` is
    its nowhere-vanishing witness `Problems.Geometry.stokes_bdry_oriented.main`. -/
noncomputable instance instBdryOriented :
    OrientedManifold (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (Bdry n M) where
  refForm := inducedOrient
  refForm_ne := Problems.Geometry.stokes_bdry_oriented.main

end Problems.Geometry.stokes_theorem
