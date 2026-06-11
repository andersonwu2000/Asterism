import Library.Geometry.Manifold.DiffFormBundle   -- DiffForm, formBundleCore, instForm*
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Calculus.DifferentialForm.Basic
import Mathlib.Analysis.Calculus.FDeriv.Basic
import Mathlib.Analysis.Calculus.FDeriv.ContinuousAlternatingMap
import Mathlib.Geometry.Manifold.ContMDiff.Atlas
import Mathlib.Geometry.Manifold.ContMDiff.Basic
import Mathlib.Geometry.Manifold.ContMDiff.NormedSpace
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.VectorBundle.Basic
import Mathlib.Geometry.Manifold.VectorBundle.Tangent
import Mathlib.Topology.VectorBundle.Basic

/-!
# Coordinate representatives of differential forms and their exterior derivatives

This file develops the coordinate-chart machinery for differential forms on a smooth manifold `M`
modelled on a normed space `E`.  The key construction is `formInCoord`, which reads a `k`-form
`φ` through a bundle trivialization to obtain a plain function `E → (E [⋀^Fin k]→L[ℝ] ℝ)`.

## Main definitions

- `formInCoord`: the coordinate representative of a differential form, obtained by reading through
  the bundle trivialization at a chart point.
- `mextDerivFun`: the raw section function of the manifold exterior derivative, transporting the
  model-space `extDerivWithin` back into the form bundle fiber.

## Main statements

- `form_in_coord_smooth`: the coordinate representative is `C^∞` on the extended-chart target.
- `form_in_coord_eq_coord_change`: evaluating `formInCoord` at a chart point equals applying
  the coordinate-change map.
- `form_in_coord_pullback`: on chart overlaps, coordinate representatives are related by the
  transition map.
- `form_in_coord_differentiable_within_range`: differentiability within `Set.range I` at the
  base point.
- `ext_deriv_locality_pullback`: the model-space exterior derivative is compatible with
  chart changes.
- `triv_read_mext_deriv_eq_coord_change`: the trivialization read of `mextDerivFun` equals the
  coordinate change of the model-space exterior derivative.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.FormCoordChange
open scoped Manifold Bundle ContDiff Topology

namespace Library.Geometry.Manifold.MExtDerivCoord

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- Coordinate representative of a `k`-form near `x`: read `φ` through the bundle
trivialization at `x`, as a function `E → (E [⋀^Fin k]→L[ℝ] ℝ)`. -/
noncomputable def formInCoord {k : ℕ} (φ : DiffForm I M k) (x : M) :
    E → (E [⋀^Fin k]→L[ℝ] ℝ) :=
  fun y ↦
    let p := (extChartAt I x).symm y
    Trivialization.continuousLinearMapAt ℝ
      (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x) p (φ p)

/-- Raw section function of the exterior derivative: apply the model `extDerivWithin`
on `range I` to the coordinate rep, transport back into the `(k+1)`-fibre. -/
noncomputable def mextDerivFun {k : ℕ} (φ : DiffForm I M k) (x : M) :
    (formBundleCore (M := M) I (k + 1)).Fiber x :=
  Trivialization.symmL ℝ
    (trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ) (formBundleCore (M := M) I (k + 1)).Fiber x) x
    (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x))

/-- Smooth vector bundle instance for `⋀ᵏ T*M`, constructed from `formBundleCore_isContMDiff`.
Required for smoothness statements about sections of the form bundle. -/
noncomputable instance instFormBundleContMDiff (k : ℕ) :
    ContMDiffVectorBundle ∞ (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber I := by
  haveI := formBundleCore_isContMDiff (M := M) I k
  exact (formBundleCore (M := M) I k).instContMDiffVectorBundle

/-- The coordinate representative of a differential form, read through the trivialization at `x₀`,
is smooth on the source of the chart at `x₀`. -/
theorem triv_section_contmdiff_on {k : ℕ} (φ : DiffForm I M k) (x₀ : M) :
    ContMDiffOn I 𝓘(ℝ, E [⋀^Fin k]→L[ℝ] ℝ) ∞
      (fun p ↦ Trivialization.continuousLinearMapAt ℝ
        (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x₀) p (φ p))
      ((chartAt H x₀).source) := by
  have h_base : (chartAt H x₀).source ⊆
      (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ)
        (formBundleCore (M := M) I k).Fiber x₀).baseSet :=
    subset_rfl
  have h_snd : ContMDiffOn I 𝓘(ℝ, E [⋀^Fin k]→L[ℝ] ℝ) ∞
      (fun p ↦ ((trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ)
          (formBundleCore (M := M) I k).Fiber x₀) ⟨p, φ p⟩).2)
      ((chartAt H x₀).source) :=
    (Trivialization.contMDiffOn_section_iff _ (chartAt H x₀).open_source h_base).mp
      φ.contMDiff.contMDiffOn
  refine h_snd.congr fun p hp ↦ ?_
  exact Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ (h_base hp) (φ p)

/-- The coordinate representative `formInCoord I φ x₀` is `C^∞` on the target of the extended
chart at `x₀`. -/
theorem form_in_coord_smooth {k : ℕ} (φ : DiffForm I M k) (x₀ : M) :
    ContDiffOn ℝ ∞ (formInCoord I φ x₀) ((extChartAt I x₀).target) := by
  have h_triv : ContMDiffOn I 𝓘(ℝ, E [⋀^Fin k]→L[ℝ] ℝ) ∞
      (fun p ↦ Trivialization.continuousLinearMapAt ℝ
        (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x₀) p (φ p))
      ((chartAt H x₀).source) := triv_section_contmdiff_on I φ x₀
  have h_symm : ContMDiffOn 𝓘(ℝ, E) I ∞ (extChartAt I x₀).symm (extChartAt I x₀).target :=
    contMDiffOn_extChartAt_symm x₀
  have h_maps : Set.MapsTo (extChartAt I x₀).symm (extChartAt I x₀).target
      ((chartAt H x₀).source) := by
    intro y hy
    simpa [extChartAt_source] using (extChartAt I x₀).map_target hy
  exact contMDiffOn_iff_contDiffOn.mp (h_triv.comp h_symm h_maps)

/-- The coordinate representative at `x` evaluated at `extChartAt I x p` equals the coordinate
change applied to `φ p`. -/
theorem form_in_coord_eq_coord_change {k : ℕ} (φ : DiffForm I M k) (x : M)
    {p : M} (hp : p ∈ (chartAt H x).source) :
    formInCoord I φ x (extChartAt I x p)
      = formCoordChange I k (achart H p) (achart H x) p (φ p) := by
  have hsymm : (extChartAt I x).symm (extChartAt I x p) = p :=
    (extChartAt I x).left_inv (by simpa only [extChartAt_source] using hp)
  have key : formInCoord I φ x (extChartAt I x p)
      = Trivialization.continuousLinearMapAt ℝ
          (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x)
          p (φ p) :=
    congrArg
      (fun q : M => Trivialization.continuousLinearMapAt ℝ
        (trivializationAt (E [⋀^Fin k]→L[ℝ] ℝ) (formBundleCore (M := M) I k).Fiber x)
        q (φ q)) hsymm
  rw [key, Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ hp]
  rfl

/-- On the overlap of two chart domains, the coordinate representative at `x` equals the
coordinate representative at `x₀` pulled back via the transition map. -/
theorem form_in_coord_pullback {k : ℕ} (φ : DiffForm I M k) (x x₀ : M) (y : E)
    (hy : y ∈ (extChartAt I x).target)
    (hy' : (extChartAt I x).symm y ∈ (chartAt H x₀).source) :
    formInCoord I φ x y =
      (formInCoord I φ x₀ (extChartAt I x₀ ((extChartAt I x).symm y))).compContinuousLinearMap
        (fderivWithin ℝ (↑(extChartAt I x₀) ∘ ↑(extChartAt I x).symm) (Set.range I) y) := by
  have hy_src : (extChartAt I x).symm y ∈ (extChartAt I x).source :=
    (extChartAt I x).map_target hy
  set p := (extChartAt I x).symm y with hp_def
  have hp_x : p ∈ (chartAt H x).source := by simpa only [extChartAt_source] using hy_src
  have h_y : extChartAt I x p = y := (extChartAt I x).right_inv hy
  have hL : formInCoord I φ x y = formCoordChange I k (achart H p) (achart H x) p (φ p) := by
    rw [← h_y]
    exact form_in_coord_eq_coord_change I φ x hp_x
  have hR : formInCoord I φ x₀ (extChartAt I x₀ p)
      = formCoordChange I k (achart H p) (achart H x₀) p (φ p) :=
    form_in_coord_eq_coord_change I φ x₀ hy'
  rw [hL, hR]
  have hD : (tangentBundleCore I M).coordChange (achart H x) (achart H x₀) p
      = fderivWithin ℝ (↑(extChartAt I x₀) ∘ ↑(extChartAt I x).symm) (Set.range I) y := by
    rw [← h_y]
    exact tangentBundleCore_coordChange_achart x x₀ p
  rw [← hD]
  simp only [formCoordChange, ContinuousAlternatingMap.compContinuousLinearMapCLM_apply]
  ext m
  simp only [ContinuousAlternatingMap.compContinuousLinearMap_apply]
  congr 1
  funext i
  exact ((tangentBundleCore I M).coordChange_comp (achart H x) (achart H x₀) (achart H p) p
    ⟨⟨hp_x, hy'⟩, mem_chart_source H p⟩ (m i)).symm

/-- The coordinate representative `formInCoord I φ x` is differentiable within `Set.range I`
at the base point `extChartAt I x x`. -/
theorem form_in_coord_differentiable_within_range {k : ℕ} (φ : DiffForm I M k) (x : M) :
    DifferentiableWithinAt ℝ (formInCoord I φ x) (Set.range I) (extChartAt I x x) := by
  have h1 : ContDiffOn ℝ ∞ (formInCoord I φ x) (extChartAt I x).target :=
    form_in_coord_smooth I φ x
  have hmem : extChartAt I x x ∈ (extChartAt I x).target := mem_extChartAt_target x
  have h2 : DifferentiableWithinAt ℝ (formInCoord I φ x) (extChartAt I x).target
      (extChartAt I x x) :=
    (h1 (extChartAt I x x) hmem).differentiableWithinAt (by norm_num)
  exact h2.mono_of_mem_nhdsWithin (extChartAt_target_mem_nhdsWithin x)

/-- The exterior derivative of `formInCoord I φ x₀` at `extChartAt I x₀ x` equals that of
the pulled-back form via the transition map to the chart at `x`. -/
theorem ext_deriv_locality_pullback {k : ℕ} (φ : DiffForm I M k) (x₀ x : M)
    (hx : x ∈ (chartAt H x₀).source) :
    extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x)
      = extDerivWithin
          (fun y => (formInCoord I φ x
              ((↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) y)).compContinuousLinearMap
            (fderivWithin ℝ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (Set.range I) y))
          (Set.range I) (extChartAt I x₀ x) := by
  have hx_src : x ∈ (extChartAt I x₀).source := by
    simpa only [extChartAt_source] using hx
  have h_t : (extChartAt I x₀).target ∈ 𝓝[Set.range I] (extChartAt I x₀ x) :=
    extChartAt_target_mem_nhdsWithin' hx_src
  have h_s : (extChartAt I x₀).symm ⁻¹' (chartAt H x).source
      ∈ 𝓝[Set.range I] (extChartAt I x₀ x) :=
    nhdsWithin_le_nhds (extChartAt_preimage_mem_nhds' hx_src
      ((chartAt H x).open_source.mem_nhds (mem_chart_source H x)))
  apply Filter.EventuallyEq.extDerivWithin_eq
  · filter_upwards [h_t, h_s] with y hy hy'
    simpa only [Function.comp_apply] using
      form_in_coord_pullback (I := I) (φ := φ) (x := x₀) (x₀ := x) (y := y) hy hy'
  · have h1 : extChartAt I x₀ x ∈ (extChartAt I x₀).target :=
      (extChartAt I x₀).map_source hx_src
    have h2 : (extChartAt I x₀).symm (extChartAt I x₀ x) ∈ (chartAt H x).source := by
      rw [(extChartAt I x₀).left_inv hx_src]; exact mem_chart_source H x
    simpa only [Function.comp_apply] using
      form_in_coord_pullback (I := I) (φ := φ) (x := x₀) (x₀ := x)
        (y := extChartAt I x₀ x) h1 h2

/-- The trivialization read of `mextDerivFun` at `x₀` equals the coordinate change of
the model-space exterior derivative. -/
theorem triv_read_mext_deriv_eq_coord_change {k : ℕ} (φ : DiffForm I M k) (x₀ x : M) :
    ((trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
        (formBundleCore (M := M) I (k + 1)).Fiber x₀) ⟨x, mextDerivFun I φ x⟩).2
      = formCoordChange I (k + 1) (achart H x) (achart H x₀) x
          (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x)) := by
  simp only [mextDerivFun]
  have hmem : x ∈ (trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
      (formBundleCore (M := M) I (k + 1)).Fiber x).baseSet :=
    (formBundleCore (M := M) I (k + 1)).mem_localTrivAt_baseSet x
  have hfun : (trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
      (formBundleCore (M := M) I (k + 1)).Fiber x).symmL ℝ x =
      (formBundleCore (M := M) I (k + 1)).coordChange
        ((formBundleCore (M := M) I (k + 1)).indexAt x)
        ((formBundleCore (M := M) I (k + 1)).indexAt x) x :=
    (formBundleCore (M := M) I (k + 1)).trivializationAt_symmL hmem
  rw [hfun]
  have step1 : ∀ (z : (formBundleCore (M := M) I (k + 1)).Fiber x),
      ((trivializationAt (E [⋀^Fin (k + 1)]→L[ℝ] ℝ)
          (formBundleCore (M := M) I (k + 1)).Fiber x₀) ⟨x, z⟩).2 =
        formCoordChange I (k + 1) (achart H x) (achart H x₀) x z := fun _ ↦ rfl
  rw [step1]
  have hself :
      (formBundleCore (M := M) I (k + 1)).coordChange
        ((formBundleCore (M := M) I (k + 1)).indexAt x)
        ((formBundleCore (M := M) I (k + 1)).indexAt x) x
        (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x)) =
      extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x) :=
    (formBundleCore (M := M) I (k + 1)).coordChange_self
      ((formBundleCore (M := M) I (k + 1)).indexAt x) x
      ((formBundleCore (M := M) I (k + 1)).mem_baseSet_at x)
      (extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x))
  exact congrArg (formCoordChange I (k + 1) (achart H x) (achart H x₀) x) hself

end Library.Geometry.Manifold.MExtDerivCoord
