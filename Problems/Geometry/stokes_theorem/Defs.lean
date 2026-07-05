/-
  Defs.lean — assembles the final inputs to the generalized Stokes theorem from the
  tower's Library:
    * `pullbackBdry` (= `ι*`): P10's `pullbackBdryFun` + its smoothness witness
      `contMDiff_pullbackBdryFun`, as a genuine smooth `n`-form on `∂M`.
    * `instBdryOriented`: `∂M`'s `OrientedManifold` instance — `refForm` is P12b's
      `inducedOrient` (`ι_ν μ`), `refForm_ne` its nowhere-vanishing `inducedOrient_ne_zero`.
  The Root proves `∫_M dφ = ∫_∂M ι*φ`. Cites P4/P6/P10/P11/P12/P12b.
-/
import Mathlib
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBoundary.CompactBdry

namespace Problems.Geometry.stokes_theorem

variable {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
  [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
  [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]

/-- The pullback `ι* φ` of a boundary `n`-form along `ι : ∂M ↪ M`, as a genuine smooth
    `n`-form on `∂M`: P10's `pullbackBdryFun` with smoothness `contMDiff_pullbackBdryFun`. -/
noncomputable def pullbackBdry (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    DiffForm (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (Bdry n M) n where
  toFun := pullbackBdryFun φ
  contMDiff_toFun := contMDiff_pullbackBdryFun φ

/-- `M`'s orientation induces one on `∂M`: the `OrientedManifold` instance the boundary
    integral `∫_∂M` reads. `refForm` is P12b's `inducedOrient` (`ι_ν μ`); `refForm_ne` is
    its nowhere-vanishing witness `inducedOrient_ne_zero`. -/
noncomputable instance instBdryOriented :
    OrientedManifold (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (Bdry n M) where
  refForm := inducedOrient
  refForm_ne := inducedOrient_ne_zero

end Problems.Geometry.stokes_theorem
