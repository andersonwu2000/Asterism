/-
  Defs.lean — owns `inducedOrient`: the induced boundary orientation `ι_ν μ` on `∂M`
  assembled as a genuine smooth `n`-form (a `DiffForm`), from P12's POU-glued
  `inducedOrientFun` (`toFun`) + its smoothness witness `contMDiff_inducedOrientFun`
  (`contMDiff_toFun`). This is `∂M`'s reference orientation form. The Root proves
  `refForm_ne` (`ι_ν μ` vanishes nowhere) — the last obligation for the induced
  `OrientedManifold` instance, which P13 assembles. Cites P12
  (`Library.Geometry.Manifold.InducedOrient{Defs,Smooth}`), P4 (`DiffForm`), `Bdry`,
  and `∂M`'s manifold structure (`isManifold_bdry` is a global `@[instance]`).
-/
import Mathlib
import Library.Geometry.Manifold.DiffFormBundle        -- DiffForm
import Library.Geometry.Manifold.StokesIntegralDefs      -- OrientedManifold (+ refForm)
import Library.Geometry.Manifold.InducedOrientDefs       -- inducedOrientFun (P12)
import Library.Geometry.Manifold.InducedOrientSmooth      -- contMDiff_inducedOrientFun (P12)
import Library.Geometry.ManifoldBdry.BdryIsManifold       -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBoundary.CompactBdry      -- Bdry

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.Manifold.InducedOrientDefs
open Library.Geometry.Manifold.InducedOrientSmooth
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBoundary.CompactBdry

namespace Problems.Geometry.stokes_bdry_oriented

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
  [OrientedManifold (𝓡∂ (n + 1)) M]
  [T2Space (Bdry n M)] [SigmaCompactSpace (Bdry n M)]

/-- The induced boundary orientation form `ι_ν μ` on `∂M`, as a genuine smooth `n`-form:
    `toFun` is P12's POU-glued `inducedOrientFun`, the smoothness witness is
    `contMDiff_inducedOrientFun`. This is `∂M`'s reference orientation form (`refForm` of
    the induced `OrientedManifold` instance assembled in P13). -/
noncomputable def inducedOrient :
    DiffForm (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (Bdry n M) n where
  toFun := inducedOrientFun
  contMDiff_toFun := contMDiff_inducedOrientFun

end Problems.Geometry.stokes_bdry_oriented
