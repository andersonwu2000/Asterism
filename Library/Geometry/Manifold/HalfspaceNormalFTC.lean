import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.HalfspaceIntegralFTC
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.Manifold.OneSidedFTC
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Calculus.Deriv.Basic
import Mathlib.Analysis.Calculus.Deriv.Comp
import Mathlib.Analysis.Calculus.FDeriv.Basic
import Mathlib.Analysis.Calculus.FDeriv.ContinuousAlternatingMap
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.Normed.Module.Alternating.Basic
import Mathlib.Data.Fin.Tuple.Basic
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.MeasureTheory.Constructions.BorelSpace.Order
import Mathlib.MeasureTheory.Integral.Bochner.Basic
import Mathlib.MeasureTheory.Integral.Bochner.Set
import Mathlib.MeasureTheory.Measure.Lebesgue.Basic
import Mathlib.Topology.Algebra.Support
import Mathlib.Topology.Basic
import Mathlib.Topology.Closure

/-!
# Half-space normal FTC (ContDiffOn-range version)

This file establishes the fundamental theorem of calculus for the normal component of a
compactly-supported top-form coefficient on the half-space `range (𝓡∂ (n+1)) = {y | 0 ≤ y 0}`.
The main result integrates the `i = 0` (normal direction) `fderivWithin`-term over the half-space
and identifies it with minus the boundary face integral, using only one-sided smoothness
`ContDiffOn ℝ ∞ w (range (𝓡∂ (n+1)))` rather than global `ContDiff`.

## Main statements

- `affine_slice_deriv_eq_fderiv`: affine chain rule — `deriv (g ∘ (s ↦ s•v+c)) = fderiv g v`.
- `range_mem_nhds_of_normal_pos`: for `x > 0`, the point `x•e₀ + faceEmbedL t` lies in the
  interior of `range (𝓡∂ (n+1))`, hence the range is a neighbourhood.
- `halfspace_normal_fderivWithin_integral_eq_neg_face_on`: the integral of the normal
  `fderivWithin`-term over `{y | 0 ≤ y 0}` equals minus the face integral over `ℝⁿ`.
-/

open Bundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.HalfspaceIntegralFTC
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.Manifold.OneSidedFTC
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open MeasureTheory
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.HalfspaceNormalFTC

/-- Affine chain rule: the derivative of `g ∘ (s ↦ s•v + c)` at `x` equals `fderiv ℝ g · v`. -/
theorem affine_slice_deriv_eq_fderiv {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    (g : E → ℝ) (c v : E) (x : ℝ) (hg : DifferentiableAt ℝ g (x • v + c)) :
    deriv (fun s : ℝ => g (s • v + c)) x = fderiv ℝ g (x • v + c) v := by
  have h1 : HasDerivAt (fun s : ℝ => s • v + c) v x := by
    have hsmul : HasDerivAt (fun s : ℝ => s • v) v x := by
      simpa using (hasDerivAt_id x).smul_const v
    simpa using hsmul.const_add c
  have h2 : HasDerivAt (fun s : ℝ => g (s • v + c)) (fderiv ℝ g (x • v + c) v) x :=
    hg.hasFDerivAt.comp_hasDerivAt x h1
  exact h2.deriv

/-- `DifferentiableAt` for fixed-tuple evaluation of a `ContDiffOn` alternating-map-valued
function, obtained by composing with the evaluation CLM `ContinuousAlternatingMap.apply`. -/
theorem differentiableAt_eval_form {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1))))
    (p : EuclideanSpace ℝ (Fin (n + 1)))
    (hmem : Set.range (𝓡∂ (n + 1)) ∈ nhds p) :
    DifferentiableAt ℝ
      (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) p := by
  have hw_diff : DifferentiableAt ℝ w p :=
    (hw.contDiffAt hmem).differentiableAt (by norm_num)
  exact hw_diff.continuousAlternatingMap_apply (fun i => differentiableAt_const _)

/-- For `x > 0`, the point `x • e₀ + faceEmbedL t` lies in the interior of `range (𝓡∂ (n+1))`
(since `faceEmbedL` has zero 0-coordinate, the 0-coordinate of the point equals `x`), so
`range (𝓡∂ (n+1))` is a neighbourhood of that point. -/
theorem range_mem_nhds_of_normal_pos {n : ℕ}
    (t : EuclideanSpace ℝ (Fin n)) (x : ℝ) (hx : 0 < x) :
    Set.range (𝓡∂ (n + 1)) ∈ nhds
      (x • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t) := by
  have hcoord : (x • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 +
      (faceEmbedL t : EuclideanSpace ℝ (Fin (n + 1)))) 0 = x := by
    simp only [faceEmbedL, ContinuousLinearMap.sum_apply, ContinuousLinearMap.smulRight_apply,
               EuclideanSpace.basisFun_apply]
    simp [Fin.succ_ne_zero]
  apply Filter.mem_of_superset (IsOpen.mem_nhds isOpen_interior _) interior_subset
  rw [interior_range_modelWithCornersEuclideanHalfSpace]
  simp only [Set.mem_setOf_eq, hcoord, hx]

/-- The `e₀`-directional `fderivWithin` over `range (𝓡∂)` equals the ordinary slice `deriv`
at points where `range (𝓡∂)` is a neighbourhood (i.e. at interior half-space points). -/
theorem fderivWithin_normal_eq_slice_deriv {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1))))
    (t : EuclideanSpace ℝ (Fin n)) (x : ℝ)
    (hmem : Set.range (𝓡∂ (n + 1)) ∈ nhds
      (x • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)) :
    fderivWithin ℝ
        (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
        (Set.range (𝓡∂ (n + 1)))
        (x • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
        (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)
      = deriv (fun s : ℝ =>
          w (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
            (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) x := by
  have hdiff : DifferentiableAt ℝ
      (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
      (x • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t) :=
    differentiableAt_eval_form w hw _ hmem
  have hcr : deriv (fun s : ℝ =>
        (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
          (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)) x
      = fderiv ℝ (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
          (x • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
          (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0) :=
    affine_slice_deriv_eq_fderiv _ (faceEmbedL t)
      (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0) x hdiff
  rw [fderivWithin_of_mem_nhds hmem]
  exact hcr.symm

/-- The `(-1)^0`-weighted normal `fderivWithin` equals the slice `deriv` at interior points
`x•e₀ + faceEmbedL t` with `x > 0`.  The sign factor `(-1)^0 = 1` is absorbed by `simpa`. -/
theorem normal_fderivWithin_eq_slice_deriv_interior {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (_hwsupp : HasCompactSupport w)
    (t : EuclideanSpace ℝ (Fin n)) (x : ℝ) (hx : 0 < x) :
    ((-1 : ℝ)) ^ ((0 : Fin (n + 1)) : ℕ) •
      fderivWithin ℝ
        (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
        (Set.range (𝓡∂ (n + 1)))
        (x • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
        (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)
      = deriv (fun s : ℝ =>
          w (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
            (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) x := by
  have hmem := range_mem_nhds_of_normal_pos t x hx
  have key := fderivWithin_normal_eq_slice_deriv w hw t x hmem
  simpa using key

/-- The function `z ↦ w z (basis tuple)` has compact support whenever `w` does,
since its support is contained in the support of `w`. -/
theorem eval_hasCompactSupport {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hwsupp : HasCompactSupport w) :
    HasCompactSupport
      (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) := by
  apply hwsupp.mono
  intro z hz
  simp only [Function.mem_support] at hz ⊢
  intro h
  apply hz
  simp [h]

/-- The function `z ↦ w z (basis tuple)` is `ContDiffOn` on `range (𝓡∂)` whenever `w` is,
obtained by composing `w` with the evaluation CLM `ContinuousAlternatingMap.apply`. -/
theorem eval_contDiffOn {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) :
    ContDiffOn ℝ ∞
      (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
      (Set.range (𝓡∂ (n + 1))) := by
  let v := Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)
  let L := ContinuousAlternatingMap.apply ℝ (EuclideanSpace ℝ (Fin (n + 1))) ℝ v
  apply ContDiffOn.comp L.contDiff.contDiffOn hw
  exact Set.mapsTo_univ _ _

/-- The slice `s ↦ g (s•e₀ + faceEmbedL t)` is `ContDiffOn ℝ ∞` on `Set.Ici 0`, obtained by
composing `hg` with the affine line map, which sends `Ici 0` into `range (𝓡∂)` since the
0-coordinate of `s•e₀ + faceEmbedL t` equals `s`. -/
theorem slice_contDiffOn_ici {n : ℕ}
    (g : EuclideanSpace ℝ (Fin (n + 1)) → ℝ)
    (hg : ContDiffOn ℝ ∞ g (Set.range (𝓡∂ (n + 1))))
    (t : EuclideanSpace ℝ (Fin n)) :
    ContDiffOn ℝ ∞ (fun s : ℝ =>
        g (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)) (Set.Ici 0) := by
  apply hg.comp (f := fun s => s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
  · apply ContDiff.contDiffOn
    fun_prop
  · intro s hs
    haveI : NeZero (n + 1) := ⟨Nat.succ_ne_zero n⟩
    rw [range_modelWithCornersEuclideanHalfSpace]
    simp only [Set.mem_setOf_eq]
    have key : (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t) 0 = s := by
      simp [faceEmbedL, EuclideanSpace.basisFun_apply, Fin.ext_iff]
    simp only [Set.mem_Ici] at hs
    linarith [key]

/-- One-sided per-slice FTC: the integral over `Ioi 0` of the slice derivative equals
`-g (faceEmbedL t)`.  The slice is `ContDiffOn` on `Ici 0` (not globally smooth) and
has compact support, so this uses the one-sided FTC `one_sided_ftc_compact`. -/
theorem slice_deriv_integral_eq_neg_on {n : ℕ}
    (g : EuclideanSpace ℝ (Fin (n + 1)) → ℝ)
    (hg : ContDiffOn ℝ ∞ g (Set.range (𝓡∂ (n + 1))))
    (hsupp : HasCompactSupport g)
    (t : EuclideanSpace ℝ (Fin n)) :
    (∫ x in Set.Ioi (0 : ℝ),
        deriv (fun s : ℝ =>
            g (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)) x
      ∂MeasureTheory.volume) = - g (faceEmbedL t) := by
  have h_cd : ContDiffOn ℝ ∞ (fun s : ℝ =>
      g (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)) (Set.Ici 0) :=
    slice_contDiffOn_ici g hg t
  have h_cs : HasCompactSupport (fun s : ℝ =>
      g (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)) :=
    slice_compact_support g hsupp t
  have key := one_sided_ftc_compact h_cd h_cs
  simpa only [zero_smul, zero_add] using key

/-- Per-slice one-sided FTC for the form-valued rep `w`: the integral over `Ioi 0` of the
slice derivative of `z ↦ w z (basis tuple)` equals minus the boundary value.
Reduces form evaluation to its scalar counterpart `slice_deriv_integral_eq_neg_on`. -/
theorem slice_fderivWithin_integral_eq_neg_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (t : EuclideanSpace ℝ (Fin n)) :
    (∫ x in Set.Ioi (0 : ℝ),
        deriv (fun s : ℝ =>
            w (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
              (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) x
        ∂MeasureTheory.volume)
      = - w (faceEmbedL t) (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)) := by
  have hg_cd := eval_contDiffOn w hw
  have hg_cs := eval_hasCompactSupport w hwsupp
  exact slice_deriv_integral_eq_neg_on
    (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) hg_cd hg_cs t

/-- Each `fderivWithin`-term `(-1)^i • fderivWithin ℝ (w · (basis tuple)) (range 𝓡∂) y (basis i)`
has compact support, since the support of the term is contained in `tsupport w`. -/
theorem halfspace_fderivWithin_term_hasCompactSupport {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (_hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (i : Fin (n + 1)) :
    HasCompactSupport
      (fun y => ((-1 : ℝ)) ^ (i : ℕ) •
        fderivWithin ℝ
          (fun z => w z (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
          (Set.range (𝓡∂ (n + 1))) y
          (EuclideanSpace.basisFun (Fin (n + 1)) ℝ i)) := by
  apply HasCompactSupport.intro' hwsupp (isClosed_tsupport w)
  intro y hyw
  have hopen : IsOpen (tsupport w)ᶜ := (isClosed_tsupport w).isOpen_compl
  have hnhd : (tsupport w)ᶜ ∈ nhds y := hopen.mem_nhds (Set.mem_compl hyw)
  have heq : (fun z => w z (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) =ᶠ[nhds y]
      (0 : EuclideanSpace ℝ (Fin (n + 1)) → ℝ) := by
    apply Filter.Eventually.mono hnhd
    intro z hz
    simp only [Pi.zero_apply]
    have h1 : z ∉ Function.support w := fun hs =>
      (Set.mem_compl_iff _ _).mp hz (subset_closure hs)
    have h2 : w z = 0 := by simpa [Function.mem_support] using h1
    rw [h2]; simp
  have hder : fderivWithin ℝ
      (fun z => w z (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
      (Set.range (𝓡∂ (n + 1))) y = 0 := by
    rw [heq.fderivWithin_eq_of_nhds]
    exact congrFun fderivWithin_zero y
  simp [hder]

/-- Each `fderivWithin`-term is continuous on the half-space `{y | 0 ≤ y 0}`.
This follows from `ContDiffOn.continuousOn_fderivWithin` applied to the evaluation
composition, using the unique differentiability of `range (𝓡∂)`. -/
theorem halfspace_fderivWithin_term_continuousOn {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (_hwsupp : HasCompactSupport w)
    (i : Fin (n + 1)) :
    ContinuousOn
      (fun y => ((-1 : ℝ)) ^ (i : ℕ) •
        fderivWithin ℝ
          (fun z => w z (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
          (Set.range (𝓡∂ (n + 1))) y
          (EuclideanSpace.basisFun (Fin (n + 1)) ℝ i))
      {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0} := by
  rw [show {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0}
      = Set.range (𝓡∂ (n + 1)) from (range_modelWithCornersEuclideanHalfSpace (n + 1)).symm]
  have hg : ContDiffOn ℝ ∞
      (fun z => w z (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
      (Set.range (𝓡∂ (n + 1))) :=
    (ContinuousAlternatingMap.apply ℝ _ ℝ
      (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))).contDiff.comp_contDiffOn hw
  have hcont := hg.continuousOn_fderivWithin (𝓡∂ (n + 1)).uniqueDiffOn (by norm_num)
  exact (hcont.clm_apply continuousOn_const).const_smul _

/-- Glue lemma: a function that is continuous on a closed set with compact support is
integrable on that set with respect to the restricted volume measure. -/
theorem integrable_restrict_of_isClosed_continuousOn_hasCompactSupport {n : ℕ}
    {f : EuclideanSpace ℝ (Fin (n + 1)) → ℝ}
    {S : Set (EuclideanSpace ℝ (Fin (n + 1)))}
    (hS : IsClosed S) (hf : ContinuousOn f S) (hsupp : HasCompactSupport f) :
    MeasureTheory.Integrable f (MeasureTheory.volume.restrict S) :=
  continuousOn_integrableOn_of_isClosed_hasCompactSupport hf hS hsupp

/-- Each `fderivWithin`-term is integrable on the half-space `{y | 0 ≤ y 0}`.
The term is continuous on the closed half-space
(`halfspace_fderivWithin_term_continuousOn`) and compactly supported
(`halfspace_fderivWithin_term_hasCompactSupport`), so integrability follows from
`integrable_restrict_of_isClosed_continuousOn_hasCompactSupport`. -/
theorem halfspace_fderivWithin_term_integrable_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (i : Fin (n + 1)) :
    MeasureTheory.Integrable
      (fun y => ((-1 : ℝ)) ^ (i : ℕ) •
        fderivWithin ℝ
          (fun z => w z (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
          (Set.range (𝓡∂ (n + 1))) y
          (EuclideanSpace.basisFun (Fin (n + 1)) ℝ i))
      (MeasureTheory.volume.restrict {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0}) := by
  have hclosed : IsClosed {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0} :=
    isClosed_le continuous_const (by fun_prop)
  exact integrable_restrict_of_isClosed_continuousOn_hasCompactSupport hclosed
    (halfspace_fderivWithin_term_continuousOn w hw hwsupp i)
    (halfspace_fderivWithin_term_hasCompactSupport w hw hwsupp i)

/-- The finite sum of `fderivWithin`-terms commutes with the half-space integral:
`∫ ∑ᵢ fᵢ = ∑ᵢ ∫ fᵢ` on `volume.restrict {y | 0 ≤ y 0}`.
This is a pure measure-theory interchange via `MeasureTheory.integral_finsetSum`. -/
theorem halfspace_div_fderivWithin_finsetSum_swap_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w) :
    ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
        (∑ i : Fin (n + 1),
            ((-1 : ℝ)) ^ (i : ℕ) •
              fderivWithin ℝ
                (fun z => w z (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
                (Set.range (𝓡∂ (n + 1))) y
                (EuclideanSpace.basisFun (Fin (n + 1)) ℝ i)) ∂MeasureTheory.volume
      = ∑ i : Fin (n + 1), ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
            ((-1 : ℝ)) ^ (i : ℕ) •
              fderivWithin ℝ
                (fun z => w z (i.removeNth (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
                (Set.range (𝓡∂ (n + 1))) y
            (EuclideanSpace.basisFun (Fin (n + 1)) ℝ i) ∂MeasureTheory.volume := by
  have h_integ := halfspace_fderivWithin_term_integrable_on w hw hwsupp
  exact MeasureTheory.integral_finsetSum Finset.univ (fun i _ => h_integ i)

/-- The `i = 0` (normal direction) `fderivWithin`-term integrated over the half-space equals the
iterated integral `∫_t ∫_{x>0} deriv (slice_t) x`, via a measure-preserving change of variables
`y = x•e₀ + faceEmbedL t` and the interior chain-rule identity
`normal_fderivWithin_eq_slice_deriv_interior`. -/
theorem halfspace_normal_fderivWithin_eq_iterated_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w) :
    ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
        ((-1 : ℝ)) ^ ((0 : Fin (n + 1)) : ℕ) •
          fderivWithin ℝ
            (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
            (Set.range (𝓡∂ (n + 1))) y
            (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0) ∂MeasureTheory.volume
      = ∫ t : EuclideanSpace ℝ (Fin n),
          (∫ x in Set.Ioi (0 : ℝ),
            deriv (fun s : ℝ =>
                w (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
                  (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) x
            ∂MeasureTheory.volume) ∂MeasureTheory.volume := by
  have hcont := halfspace_fderivWithin_term_continuousOn w hw hwsupp 0
  have hsupp := halfspace_fderivWithin_term_hasCompactSupport w hw hwsupp 0
  rw [halfspace_within_integral_change_var _ hcont hsupp]
  refine integral_congr_ae (Filter.Eventually.of_forall fun t => ?_)
  refine setIntegral_congr_fun measurableSet_Ioi (fun x hx => ?_)
  exact normal_fderivWithin_eq_slice_deriv_interior w hw hwsupp t x hx

/-- **Half-space normal FTC** (ContDiffOn-range version): the integral of the `i = 0`
`fderivWithin`-term over `{y | 0 ≤ y 0}` equals minus the face integral of
`w (faceEmbedL t) (basis tuple)` over `ℝⁿ`.
Proof: change variables to the iterated form via
`halfspace_normal_fderivWithin_eq_iterated_on`, then apply the per-slice FTC
`slice_fderivWithin_integral_eq_neg_on`, then `integral_neg`. -/
theorem halfspace_normal_fderivWithin_integral_eq_neg_face_on {n : ℕ}
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w) :
    ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
        ((-1 : ℝ)) ^ ((0 : Fin (n + 1)) : ℕ) •
          fderivWithin ℝ
            (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
            (Set.range (𝓡∂ (n + 1))) y
            (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0) ∂MeasureTheory.volume
      = - ∫ t : EuclideanSpace ℝ (Fin n),
          w (faceEmbedL t)
            (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)) ∂MeasureTheory.volume := by
  have h_iter : ∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
        ((-1 : ℝ)) ^ ((0 : Fin (n + 1)) : ℕ) •
          fderivWithin ℝ
            (fun z => w z (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)))
            (Set.range (𝓡∂ (n + 1))) y
            (EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0) ∂MeasureTheory.volume
      = ∫ t : EuclideanSpace ℝ (Fin n),
          (∫ x in Set.Ioi (0 : ℝ),
            deriv (fun s : ℝ =>
                w (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
                  (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) x
            ∂MeasureTheory.volume) ∂MeasureTheory.volume :=
    halfspace_normal_fderivWithin_eq_iterated_on w hw hwsupp
  have h_slice : ∀ t : EuclideanSpace ℝ (Fin n),
      (∫ x in Set.Ioi (0 : ℝ),
          deriv (fun s : ℝ =>
              w (s • EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0 + faceEmbedL t)
                (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))) x
          ∂MeasureTheory.volume)
        = - w (faceEmbedL t) (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)) :=
    slice_fderivWithin_integral_eq_neg_on w hw hwsupp
  rw [h_iter]
  simp_rw [h_slice]
  rw [MeasureTheory.integral_neg]

end Library.Geometry.Manifold.HalfspaceNormalFTC
