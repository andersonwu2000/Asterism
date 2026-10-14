/-
  Defs.lean — owns `inducedOrient`: the induced boundary orientation `ι_ν μ` on `∂M`
  assembled as a genuine smooth `n`-form (a `DiffForm`), from P12's POU-glued
  `inducedOrientFun` (`toFun`) + its smoothness witness `Problems.Geometry.stokes_induced_orient.main`
  (`contMDiff_toFun`). This is `∂M`'s reference orientation form. The Root proves
  `refForm_ne` (`ι_ν μ` vanishes nowhere) — the last obligation for the induced
  `OrientedManifold` instance, which P13 assembles. Cites P12
  (`Problems.Geometry.stokes_induced_orient`), P4 (`DiffForm`), `Bdry`,
  and `∂M`'s manifold structure (`isManifold_bdry` is a global `@[instance]`).
-/
import Mathlib
import Problems.Geometry.stokes_bdry_chart.proofs.L_boundary_ext_chart_at_coord_zero
import Problems.Geometry.stokes_bdry_compact.Defs
import Problems.Geometry.stokes_bdry_manifold.Defs
import Problems.Geometry.stokes_bdry_manifold.Root
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_form_coord_comp.Defs
import Problems.Geometry.stokes_form_coord_self.Root
import Problems.Geometry.stokes_induced_orient.Defs
import Problems.Geometry.stokes_induced_orient.Root
import Problems.Geometry.stokes_induced_orient.proofs.L_chartfun_triv_read
import Problems.Geometry.stokes_integral.Defs
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_eq_coord_change
import Problems.Geometry.stokes_pullback.Defs
import Problems.Geometry.stokes_pullback.proofs.L_amb_trans_comp_face_embed_hasfderiv
import Problems.Geometry.stokes_pullback.proofs.L_amb_trans_face_embed_eventually_eq
import Problems.Geometry.stokes_pullback.proofs.L_face_embed_comp_bdry_trans_hasfderiv
import Problems.Geometry.stokes_pullback.proofs.L_form_coord_change_transport_self

open scoped Manifold Bundle ContDiff
open Bundle
open Problems.Geometry.stokes_form_bundle (DiffForm)
open Problems.Geometry.stokes_integral (OrientedManifold)
open Problems.Geometry.stokes_induced_orient (inducedOrientFun)
open Problems.Geometry.stokes_bdry_compact (Bdry)

namespace Problems.Geometry.stokes_bdry_oriented

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
  [OrientedManifold (𝓡∂ (n + 1)) M]
  [T2Space (Bdry n M)] [SigmaCompactSpace (Bdry n M)]

/-- The induced boundary orientation form `ι_ν μ` on `∂M`, as a genuine smooth `n`-form:
    `toFun` is P12's POU-glued `inducedOrientFun`, the smoothness witness is
    `Problems.Geometry.stokes_induced_orient.main`. This is `∂M`'s reference orientation form (`refForm` of
    the induced `OrientedManifold` instance assembled in P13). -/
noncomputable def inducedOrient :
    DiffForm (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (Bdry n M) n where
  toFun := inducedOrientFun
  contMDiff_toFun := Problems.Geometry.stokes_induced_orient.main

end Problems.Geometry.stokes_bdry_oriented
