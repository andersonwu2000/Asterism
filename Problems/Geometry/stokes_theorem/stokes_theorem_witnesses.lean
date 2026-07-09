/-
  stokes_theorem_witnesses.lean — a SINGLE-FILE witness that every deferred
  obligation (`sorry`) of the Stokes blueprint `stokes_theorem_reference.lean`
  is genuinely proved in the Library.

  Method: rather than re-declare the blueprint's vocabulary locally — which would
  (a) re-declare `class OrientedManifold` as a fresh nominal type the Library
  keystone can't unify against, and (b) drag the blueprint's own `sorry`s into
  every type that mentions them — this file `open`s the Library and states each
  obligation against the Library's (sorry-free) definitions. Every witness is a
  real citation, `sorryAx`-free (the `#print axioms` at the bottom show the only
  axioms are the three framework-whitelisted ones), INCLUDING `stokes`.

  Two shapes appear:
    * `theorem <name> : <obligation> := <Library proof>` — the obligation type is
      written out; the proof is the Library decl.
    * `def <name> := @<Library decl>` — a verbose-typed obligation (a bundle-
      section smoothness `ContMDiff …`, a partial-homeomorphism field law, or a
      Type-valued instance); the alias's INFERRED type IS the obligation, viewable
      via `#check <name>`.
-/
import Mathlib
import Library.Geometry.Manifold.FormCoordChange
import Library.Geometry.Manifold.FormCoordChangeSelf
import Library.Geometry.Manifold.FormCoordChangeCont
import Library.Geometry.Manifold.DiffFormBundle
import Library.Geometry.Manifold.MExtDeriv
import Library.Geometry.Manifold.DDZero
import Library.Geometry.ManifoldBoundary.CompactBdry
import Library.Geometry.ManifoldBoundary.BoundaryChart
import Library.Geometry.ManifoldBdry.BdryChart
import Library.Geometry.ManifoldBdry.ChartedBdry
import Library.Geometry.ManifoldBdry.BdryIsManifold
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff
import Library.Geometry.Manifold.InducedOrientSmooth
import Library.Geometry.Manifold.InducedOrientNonzero
import Library.Geometry.Manifold.PerBumpStokes

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.FormCoordChangeSelf
open Library.Geometry.Manifold.FormCoordChangeCont
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDeriv
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.BoundaryChart
open Library.Geometry.ManifoldBdry.BdryChart
open Library.Geometry.ManifoldBdry.ChartedBdry
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.Manifold.InducedOrientSmooth
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.Manifold.PerBumpStokes

namespace StokesBlueprintWitnesses

/-! ## §1 / §A.1–A.4 — the `⋀ᵏ T*M` form bundle -/
section FormBundle
variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

theorem A1_formCoordChange_self (k : ℕ) :
    ∀ i, ∀ x ∈ (tangentBundleCore I M).baseSet i, ∀ v,
      formCoordChange I k i i x v = v :=
  formCoordChange_self I k

theorem A2_formCoordChange_continuousOn (k : ℕ) :
    ∀ i j, ContinuousOn (formCoordChange I k i j)
      ((tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j) :=
  continuousOn_formCoordChange I k

theorem A3_formCoordChange_comp (k : ℕ) :
    ∀ i j l, ∀ x ∈ (tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j
        ∩ (tangentBundleCore I M).baseSet l, ∀ v,
      formCoordChange I k j l x (formCoordChange I k i j x v)
        = formCoordChange I k i l x v :=
  formCoordChange_comp I k

theorem A4_formBundleCore_isContMDiff (k : ℕ) :
    (formBundleCore (M := M) I k).IsContMDiff I ∞ :=
  formBundleCore_isContMDiff I k
end FormBundle

/-! ## §2 / §A.5–A.6 — exterior derivative `mextDeriv` (smoothness + d∘d=0) -/
section ExtDeriv
variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- §A.5 `mextDeriv` smoothness witness (`ContMDiff …` — see `#check`). -/
def A5_mextDeriv_contMDiff := @contMDiff_mextDerivFun

theorem A6_mextDeriv_dd {k : ℕ} (φ : DiffForm I M k) :
    mextDeriv I (mextDeriv I φ) = 0 :=
  mextDeriv_mextDeriv_eq_zero I φ
end ExtDeriv

/-! ## §5 — the boundary `∂M` as a charted `n`-manifold

    The blueprint's `bdryChart` inlines 8 partial-homeomorphism field `sorry`s
    plus the `invFun`-membership and `ChartedSpace.mem_chart_source` ones; the
    Library discharges each as a named lemma on its (sorry-free) `bdryChart`. -/
section Boundary
variable {n : ℕ}
  {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
  [IsManifold (𝓡∂ (n + 1)) ∞ M]

-- bdryChart PartialEquiv laws  (blueprint map_source'/map_target'/left_inv'/right_inv')
def B5_chart_map_source := @chart_map_source
def B5_chart_map_target := @chart_map_target
def B5_chart_left_inv := @chart_left_inv
def B5_chart_right_inv := @chart_right_inv
-- bdryChart topology laws  (blueprint open_source/open_target/continuousOn_to/invFun)
def B5_isOpen_chartSource := @isOpen_chartSource
def B5_isOpen_chartTarget := @isOpen_chartTarget
def B5_continuousOn_chartToFun := @continuousOn_chartToFun
def B5_continuousOn_chartInvFun := @continuousOn_chartInvFun
-- ChartedSpace.mem_chart_source obligation
def B5_mem_bdryChart_source := @mem_bdryChart_source
-- §5 ∂M is a charted space over EuclideanSpace ℝ (Fin n)  (Type-valued instance)
noncomputable def B5_instBdryChartedSpace := @instBdryChartedSpace

/-- §5 `instBdryManifold`: `∂M` is a `C^∞` manifold. -/
theorem B5_isManifold_bdry :
    IsManifold (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) ∞ (Bdry n M) := isManifold_bdry

/-- §A.7 `pullbackBdry` smoothness witness (`ContMDiff …` — see `#check`). -/
def B5_pullbackBdry_contMDiff := @contMDiff_pullbackBdryFun
end Boundary

/-! ## §6 — induced orientation, compactness, and STOKES -/
section StokesThm
variable {n : ℕ}
  {M : Type*} [TopologicalSpace M] [T2Space M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
  [IsManifold (𝓡∂ (n + 1)) ∞ M] [CompactSpace M] [OrientedManifold (𝓡∂ (n + 1)) M]

/-- §6 `instBdryCompact`: `∂M` is compact. -/
theorem B6_compactSpace_bdry : CompactSpace (Bdry n M) := compactSpace_bdry

/-- §6 induced-orientation smoothness witness (`inducedOrient`'s deferred Prop). -/
def B6_inducedOrient_contMDiff := @contMDiff_inducedOrientFun

/-- §6 `instBdryOriented.refForm_ne`: the induced orientation vanishes nowhere. -/
def B6_inducedOrient_ne_zero := @inducedOrient_ne_zero

/-- §6 STOKES — `∫_M dφ = ∫_∂M ι*φ`, the blueprint root, proved sorry-free. -/
theorem B6_stokes [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    DiffForm.integral (mextDeriv (𝓡∂ (n + 1)) φ) = DiffForm.integral (pullbackBdry φ) :=
  integral_mextDeriv_eq_integral_pullbackBdry φ
end StokesThm

end StokesBlueprintWitnesses

-- sorry-free confirmation (representative spread across all sections; every other
-- witness is the same shape — a citation of a sorry-free Library decl).
#print axioms StokesBlueprintWitnesses.A3_formCoordChange_comp
#print axioms StokesBlueprintWitnesses.A5_mextDeriv_contMDiff
#print axioms StokesBlueprintWitnesses.A6_mextDeriv_dd
#print axioms StokesBlueprintWitnesses.B5_chart_left_inv
#print axioms StokesBlueprintWitnesses.B5_isManifold_bdry
#print axioms StokesBlueprintWitnesses.B5_pullbackBdry_contMDiff
#print axioms StokesBlueprintWitnesses.B6_inducedOrient_ne_zero
#print axioms StokesBlueprintWitnesses.B6_stokes
