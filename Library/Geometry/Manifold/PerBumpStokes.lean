import Library.Geometry.Manifold.DDZero
import Library.Geometry.Manifold.DDZero                       -- mextDeriv
import Library.Geometry.Manifold.DiffFormBundle
import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.HalfspaceTangentialFTC
import Library.Geometry.Manifold.InducedOrientNonzero         -- inducedOrient, inducedOrient_ne_zero
import Library.Geometry.Manifold.MExtDerivCoord
import Library.Geometry.Manifold.RefFormSign
import Library.Geometry.Manifold.SingleChartCollapse
import Library.Geometry.Manifold.StokesIntegral
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Library.Geometry.ManifoldBdry.BdryIsManifold           -- isManifold_bdry (instance)
import Library.Geometry.ManifoldBdry.ChartedBdry
import Library.Geometry.ManifoldBdry.FaceEmbedLemmas
import Library.Geometry.ManifoldBdry.PullbackBdryDefs
import Library.Geometry.ManifoldBdry.PullbackBdryDefs         -- pullbackBdryFun
import Library.Geometry.ManifoldBdry.PullbackFormContMDiff    -- contMDiff_pullbackBdryFun
import Library.Geometry.ManifoldBoundary.CompactBdry          -- Bdry
import Library.Geometry.ManifoldBoundary.Defs
import Mathlib.Algebra.BigOperators.Finprod
import Mathlib.Algebra.Group.Indicator
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Calculus.FDeriv.Basic
import Mathlib.Analysis.Calculus.FDeriv.ContinuousAlternatingMap
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.NormedSpace.Multilinear.Basic
import Mathlib.Data.Fin.Basic
import Mathlib.Data.Real.Sign
import Mathlib.Geometry.Manifold.BumpFunction
import Mathlib.Geometry.Manifold.ContMDiff.Basic
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.InteriorBoundary
import Mathlib.Geometry.Manifold.PartitionOfUnity
import Mathlib.MeasureTheory.Integral.Bochner.Basic
import Mathlib.MeasureTheory.Measure.Lebesgue.Basic
import Mathlib.Topology.Algebra.Support
import Mathlib.Topology.Compactness.Compact
import Mathlib.Topology.Connected.Basic
import Mathlib.Topology.FiberBundle.Basic
import Mathlib.Topology.VectorBundle.Basic

open Bundle
open Library.Geometry.Manifold.DDZero
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.HalfspaceTangentialFTC
open Library.Geometry.Manifold.InducedOrientDefs
open Library.Geometry.Manifold.InducedOrientNonzero
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.RefFormSign
open Library.Geometry.Manifold.SingleChartCollapse
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.FaceEmbedLemmas
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBdry.PullbackFormContMDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open MeasureTheory
open scoped Manifold Bundle ContDiff
open scoped Manifold Bundle ContDiff Topology

namespace Library.Geometry.Manifold.PerBumpStokes

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

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

-- Forward rationale: keystone V1 for the weighted-divergence route (goal 4212
-- `lhs_finsum_face_transfer`). `ContMDiffSection` only carries the ring-scalar `SMul`,
-- not a pointwise `C^∞(M,ℝ)`-module smul, so `mextDeriv (gᵢ • φ)` with
-- `gᵢ = B.toSmoothPartitionOfUnity i` cannot even be written. This builds that
-- smooth-function smul on `DiffForm`: pointwise `g x • φ x`, smooth by
-- `ContMDiff.smul_section`. Mirrors the record-style `where toFun/contMDiff_toFun`
-- pattern of `mextDeriv` (DDZero.lean). Composes downstream with
-- `form_in_coord_mext_deriv_eq` + Mathlib's `extDerivWithin` product rule (a separate
-- Leibniz Forward to issue once this lands).
noncomputable
def smul_form {k : ℕ} (g : M → ℝ) (hg : ContMDiff I 𝓘(ℝ, ℝ) ∞ g)
    (φ : DiffForm I M k) : DiffForm I M k where
  toFun := fun x => g x • φ x
  contMDiff_toFun := ContMDiff.smul_section hg φ.contMDiff

theorem smul_form_family_finite {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type*} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    (Function.support (fun i => smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
        (B.toSmoothPartitionOfUnity i).contMDiff φ)).Finite  := by
  haveI := B.fintype
  exact Set.toFinite _

theorem smul_finsum_eq_self {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type*} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    (∑ᶠ i, smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ) = φ  := by
  have h_fin := smul_form_family_finite B φ
  ext x
  have hco := ((Pi.evalAddMonoidHom _ x).comp
      (ContMDiffSection.coeAddHom (𝓡∂ (n + 1)) _ ∞ _)).map_finsum h_fin
  simp only [AddMonoidHom.coe_comp, Function.comp_apply, ContMDiffSection.coeAddHom_apply,
    Pi.evalAddMonoidHom_apply] at hco
  rw [hco]
  have hsummand : ∀ i, (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff φ) x
      = (B.toSmoothPartitionOfUnity i) x • φ x := fun i => rfl
  have hsupp : (Function.support (fun i => (B.toSmoothPartitionOfUnity i) x)).Finite :=
    B.toSmoothPartitionOfUnity.locallyFinite.point_finite x
  rw [finsum_congr hsummand, ← finsum_smul' hsupp,
    B.toSmoothPartitionOfUnity.sum_eq_one (Set.mem_univ x), one_smul]

theorem mextderiv_finsum_additive_generic {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type*} (g : ιM → DiffForm (𝓡∂ (n + 1)) M n)
    (hg : (Function.support g).Finite) :
    mextDeriv (𝓡∂ (n + 1)) (∑ᶠ i, g i) = ∑ᶠ i, mextDeriv (𝓡∂ (n + 1)) (g i)  := by
  set I := 𝓡∂ (n + 1) with hI
  -- binary additivity of mextDeriv
  have hadd : ∀ a b : DiffForm I M n,
      mextDeriv I (a + b) = mextDeriv I a + mextDeriv I b := by
    intro a b
    refine ContMDiffSection.ext fun x => ?_
    have hfc : formInCoord I (a + b) x
        = formInCoord I a x + formInCoord I b x := by
      funext y
      simp only [formInCoord, ContMDiffSection.coe_add, Pi.add_apply, map_add]
    have hda := form_in_coord_differentiable_within_range I a x
    have hdb := form_in_coord_differentiable_within_range I b x
    have hz : extChartAt I x x ∈ Set.range I :=
      extChartAt_target_subset_range x (mem_extChartAt_target x)
    have huniq : UniqueDiffWithinAt ℝ (Set.range I) (extChartAt I x x) :=
      I.uniqueDiffOn _ hz
    change mextDerivFun I (a + b) x = mextDerivFun I a x + mextDerivFun I b x
    rw [mextDerivFun, mextDerivFun, mextDerivFun, hfc,
      extDerivWithin_add huniq hda hdb, ContinuousLinearMap.map_add]
  -- mextDeriv sends 0 to 0
  have hzero : mextDeriv I (0 : DiffForm I M n) = 0 := by
    refine ContMDiffSection.ext fun x => ?_
    change mextDerivFun I (0 : DiffForm I M n) x = 0
    have hfc : formInCoord I (0 : DiffForm I M n) x = 0 := by
      funext z
      simp only [formInCoord, ContMDiffSection.coe_zero, Pi.zero_apply, map_zero]
    rw [mextDerivFun, hfc]
    simp only [extDerivWithin, Pi.zero_def, fderivWithin_const_apply,
      ← ContinuousAlternatingMap.alternatizeUncurryFinCLM_apply, ContinuousLinearMap.map_zero]
  let F : DiffForm I M n →+ DiffForm I M (n + 1) :=
    { toFun := mextDeriv I
      map_zero' := hzero
      map_add' := hadd }
  exact F.map_finsum hg

theorem mextderiv_smul_support_subset {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type*} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    (Function.support (fun i => mextDeriv (𝓡∂ (n + 1))
      (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
        (B.toSmoothPartitionOfUnity i).contMDiff φ)))
      ⊆ {i | (Function.support (fun x => (B.toSmoothPartitionOfUnity i) x)).Nonempty}  := by
  intro i hi
  rw [Function.mem_support] at hi
  by_contra hne
  simp only [Set.mem_setOf_eq, Set.not_nonempty_iff_eq_empty,
    Function.support_eq_empty_iff] at hne
  apply hi
  have hsf : smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff φ = 0 := by
    refine ContMDiffSection.ext fun x => ?_
    change (B.toSmoothPartitionOfUnity i) x • φ x = (0 : DiffForm (𝓡∂ (n + 1)) M n) x
    rw [show (B.toSmoothPartitionOfUnity i) x = 0 from congrFun hne x]
    simp
  rw [hsf]
  refine ContMDiffSection.ext fun x => ?_
  change Library.Geometry.Manifold.MExtDerivCoord.mextDerivFun
    (𝓡∂ (n + 1)) (0 : DiffForm (𝓡∂ (n + 1)) M n) x = 0
  have hfc : Library.Geometry.Manifold.MExtDerivCoord.formInCoord
      (𝓡∂ (n + 1)) (0 : DiffForm (𝓡∂ (n + 1)) M n) x = 0 := by
    funext z
    simp only [Library.Geometry.Manifold.MExtDerivCoord.formInCoord,
      ContMDiffSection.coe_zero, Pi.zero_apply, map_zero]
  rw [Library.Geometry.Manifold.MExtDerivCoord.mextDerivFun, hfc]
  simp only [extDerivWithin, Pi.zero_def, fderivWithin_const_apply,
    ← ContinuousAlternatingMap.alternatizeUncurryFinCLM_apply, ContinuousLinearMap.map_zero]

theorem bump_mextderiv_family_finite {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type*} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    (Function.support (fun i => mextDeriv (𝓡∂ (n + 1))
      (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
        (B.toSmoothPartitionOfUnity i).contMDiff φ))).Finite  := by
  have hsub := mextderiv_smul_support_subset B φ
  have hfin :
      {i | (Function.support (fun x => (B.toSmoothPartitionOfUnity i) x)).Nonempty}.Finite :=
    (B.toSmoothPartitionOfUnity.locallyFinite).finite_nonempty_of_compact
  exact hfin.subset hsub

-- Form-level (DiffForm-valued) split of `mextDeriv φ = ∑ᶠ mextDeriv (PoUᵢ • φ)` into a
-- generic linearity bridge and the partition-of-unity collapse — neither restating the parent.
--   h_sum : ∑ᶠ (PoUᵢ • φ) = φ          [smul_finsum_eq_self : ∑ᶠ PoUᵢ = 1, pointwise]
--   h_add : mextDeriv (∑ᶠ gᵢ) = ∑ᶠ mextDeriv gᵢ  [generic additivity over a finite family]
--   h_fin : the smul family has finite support  [feeds the generic bridge]
-- mextDeriv φ = mextDeriv (∑ᶠ PoUᵢ•φ) [rw h_sum] = ∑ᶠ mextDeriv (PoUᵢ•φ) [h_add].
-- `h_add` is GENERIC (abstract family g), so the T3 detector cannot substitute `h_sum` to
-- telescope it back to `main`; `h_sum` carries no `mextDeriv` so it is not the parent.
theorem mextderiv_smul_finsum_eq {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type*} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    mextDeriv (𝓡∂ (n + 1)) φ
      = ∑ᶠ i, mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ)  := by
  have h_fin : (Function.support (fun i => smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff φ)).Finite := smul_form_family_finite B φ
  have h_sum : (∑ᶠ i, smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff φ) = φ := smul_finsum_eq_self B φ
  have h_add := mextderiv_finsum_additive_generic
    (fun i => smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff φ) h_fin
  calc mextDeriv (𝓡∂ (n + 1)) φ
      = mextDeriv (𝓡∂ (n + 1)) (∑ᶠ i, smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ) := by rw [h_sum]
    _ = ∑ᶠ i, mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ) := h_add

theorem diffform_integral_add
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    (a b : DiffForm I N d) :
    DiffForm.integral (a + b) = DiffForm.integral a + DiffForm.integral b  := by
  set h := SmoothBumpCovering.exists_isSubordinate
    (I := I) (M := N) (s := Set.univ) isClosed_univ
    (U := fun x => (chartAt EH x).source)
    (fun x _ => (chartAt EH x).open_source.mem_nhds (mem_chart_source _ x)) with hh
  set B₀ := h.choose_spec.choose with hBdef
  have hsub := h.choose_spec.choose_spec
  have e_ab : DiffForm.integral (a + b)
      = ∑ᶠ i, ∫ y in (extChartAt I (B₀.c i)).target,
          B₀.toSmoothPartitionOfUnity i ((extChartAt I (B₀.c i)).symm y)
            * localCoeff (a + b) (B₀.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₀.c i) y)
            ∂volume := rfl
  have e_a : DiffForm.integral a
      = ∑ᶠ i, ∫ y in (extChartAt I (B₀.c i)).target,
          B₀.toSmoothPartitionOfUnity i ((extChartAt I (B₀.c i)).symm y)
            * localCoeff a (B₀.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₀.c i) y)
            ∂volume := rfl
  have e_b : DiffForm.integral b
      = ∑ᶠ i, ∫ y in (extChartAt I (B₀.c i)).target,
          B₀.toSmoothPartitionOfUnity i ((extChartAt I (B₀.c i)).symm y)
            * localCoeff b (B₀.c i) y
            * Real.sign (localCoeff (OrientedManifold.refForm (I := I) (N := N)) (B₀.c i) y)
            ∂volume := rfl
  rw [e_ab, e_a, e_b]
  exact integral_add_over_covering a b B₀ hsub

theorem diffform_integral_finsum_additive
    {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [T2Space N] [ChartedSpace EH N]
    [IsManifold I ∞ N] [CompactSpace N] [OrientedManifold I N]
    {ι : Type*} (g : ι → DiffForm I N d) (hg : (Function.support g).Finite) :
    DiffForm.integral (∑ᶠ i, g i) = ∑ᶠ i, DiffForm.integral (g i)  := by
  have h_add : ∀ a b : DiffForm I N d,
      DiffForm.integral (a + b) = DiffForm.integral a + DiffForm.integral b :=
    fun a b => diffform_integral_add a b
  let F : DiffForm I N d →+ ℝ :=
    { toFun := DiffForm.integral
      map_zero' := Library.Geometry.Manifold.StokesIntegral.integral_zero
      map_add' := h_add }
  exact F.map_finsum hg

-- mextderiv_vanish_off_tsupport: mextDeriv I φ x = 0 when x ∉ tsupport φ;
-- mirrors fderiv_of_notMem_tsupport via notMem_tsupport_iff_eventuallyEq +
-- chart-symm continuity + EventuallyEq.extDerivWithin_eq_nhds
set_option maxHeartbeats 400000 in
-- complex bundle fibers require extra heartbeats for typeclass resolution
theorem mextderiv_vanish_off_tsupport
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k)
    (x : M) (hx : x ∉ tsupport (fun y => φ y)) :
    mextDeriv I φ x = 0 := by
  change mextDerivFun I φ x = 0
  simp only [mextDerivFun]
  have hφ_eq : (fun y => φ y) =ᶠ[nhds x] 0 := notMem_tsupport_iff_eventuallyEq.mp hx
  have htend : Filter.Tendsto (extChartAt I x).symm (nhds (extChartAt I x x)) (nhds x) := by
    conv_rhs => rw [← (extChartAt I x).left_inv (mem_extChartAt_source x)]
    exact (continuousAt_extChartAt_symm x).tendsto
  have hφ : ∀ᶠ y in nhds (extChartAt I x x), φ ((extChartAt I x).symm y) = 0 :=
    hφ_eq.comp_tendsto htend
  have hfc : formInCoord I φ x =ᶠ[nhds (extChartAt I x x)] 0 := by
    filter_upwards [hφ] with y hy
    simp only [formInCoord, Pi.zero_apply, hy, map_zero]
  have h0 : extDerivWithin (formInCoord I φ x) (Set.range I) (extChartAt I x x) = 0 := by
    rw [hfc.extDerivWithin_eq_nhds]
    simp only [extDerivWithin, Pi.zero_def, fderivWithin_fun_const]
    exact (ContinuousAlternatingMap.alternatizeUncurryFinCLM ℝ E ℝ).map_zero
  rw [h0]
  exact ContinuousLinearMap.map_zero _

-- Locality of the manifold exterior derivative: tsupport(mextDeriv φ) ⊆ tsupport(φ).
-- Mirrors Mathlib `tsupport_fderiv_subset`: reduce to support ⊆ tsupport(φ) via
-- `closure_minimal` + `isClosed_tsupport`, then the single Builder leaf
-- `mextderiv_vanish_off_tsupport` (off tsupport φ, φ =ᶠ[𝓝 x] 0 ⇒ extDerivWithin = 0).
theorem mextderiv_tsupport_subset
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) :
    tsupport (fun x => (mextDeriv I φ) x) ⊆ tsupport (fun x => φ x)  := by
  apply closure_minimal _ (isClosed_tsupport _)
  intro x hx
  by_contra hc
  exact hx (mextderiv_vanish_off_tsupport I φ x hc)

-- mextderiv_smul_tsupport_subset: mextDeriv locality + smul left support bound.
-- Chain: mextderiv_tsupport_subset gives tsupport(mextDeriv(g•φ)) ⊆ tsupport(g•φ);
-- tsupport_smul_subset_left gives ⊆ tsupport g; hsupp closes.
theorem mextderiv_smul_tsupport_subset {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    tsupport (fun x => (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) x)
      ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source := by
  calc tsupport (fun x => (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) x)
      ⊆ tsupport (fun x => (smul_form (𝓡∂ (n + 1)) g hg φ) x) :=
          mextderiv_tsupport_subset (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)
    _ ⊆ tsupport (fun x => g x) :=
          tsupport_smul_subset_left (fun x => g x) (fun x => φ x)
    _ ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source := hsupp

-- coord_indicator_contdiffwithinat_off_target_pt: off-target indicator is ContDiffWithinAt via
-- tsupport ⊆ target ⇒ x ∉ tsupport ⇒ indicator =ᶠ 0 near x ⇒ contDiffWithinAt_const
theorem coord_indicator_contdiffwithinat_off_target_pt {n : ℕ} {M : Type*} [TopologicalSpace M]
    [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n)
    (htsub : tsupport ((extChartAt (𝓡∂ (n + 1)) c₀).target.indicator
        (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
          (smul_form (𝓡∂ (n + 1)) g hg φ) c₀)) ⊆
        (extChartAt (𝓡∂ (n + 1)) c₀).target) :
    ∀ x ∈ Set.range (𝓡∂ (n + 1)),
      x ∉ (extChartAt (𝓡∂ (n + 1)) c₀).target →
      ContDiffWithinAt ℝ ∞ ((extChartAt (𝓡∂ (n + 1)) c₀).target.indicator
        (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
          (smul_form (𝓡∂ (n + 1)) g hg φ) c₀)) (Set.range (𝓡∂ (n + 1))) x := by
    intro x _ hnot
    set f := (extChartAt (𝓡∂ (n + 1)) c₀).target.indicator
        (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
          (smul_form (𝓡∂ (n + 1)) g hg φ) c₀) with hf_def
    have hxts : x ∉ tsupport f := fun h => hnot (htsub h)
    have hclosed : IsClosed (tsupport f) := isClosed_closure
    apply (contDiffWithinAt_const (c := 0)).congr_of_eventuallyEq _
      (Set.indicator_of_notMem hnot _)
    apply Filter.Eventually.filter_mono nhdsWithin_le_nhds
    filter_upwards [hclosed.isOpen_compl.mem_nhds hxts] with y hy
    have hny : y ∉ tsupport f := (Set.mem_compl_iff _ _).mp hy
    exact Function.notMem_support.mp (fun h => hny (subset_tsupport f h))

-- coord_indicator_contdiffwithinat_at_target_pt: when x ∈ target, the indicator equals
-- formInCoord which is ContDiffOn target (form_in_coord_smooth); transported to range I via
-- extChartAt_target_mem_nhdsWithin_of_mem, then congr swaps formInCoord → indicator.
theorem coord_indicator_contdiffwithinat_at_target_pt {n : ℕ} {M : Type*} [TopologicalSpace M]
    [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    ∀ x ∈ Set.range (𝓡∂ (n + 1)),
      x ∈ (extChartAt (𝓡∂ (n + 1)) c₀).target →
      ContDiffWithinAt ℝ ∞ ((extChartAt (𝓡∂ (n + 1)) c₀).target.indicator
        (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
          (smul_form (𝓡∂ (n + 1)) g hg φ) c₀)) (Set.range (𝓡∂ (n + 1))) x := by
  intro x _hx htarget
  have hfic : ContDiffWithinAt ℝ ∞
      (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀)
      (extChartAt (𝓡∂ (n + 1)) c₀).target x :=
    ContDiffOn.contDiffWithinAt
      (Library.Geometry.Manifold.MExtDerivCoord.form_in_coord_smooth (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀)
      htarget
  have htarget_nhd : (extChartAt (𝓡∂ (n + 1)) c₀).target ∈ 𝓝[Set.range (𝓡∂ (n + 1))] x :=
    extChartAt_target_mem_nhdsWithin_of_mem htarget
  have hfic_rangeI : ContDiffWithinAt ℝ ∞
      (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀)
      (Set.range (𝓡∂ (n + 1))) x :=
    hfic.mono_of_mem_nhdsWithin htarget_nhd
  have heq : (extChartAt (𝓡∂ (n + 1)) c₀).target.indicator
      (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀) =ᶠ[𝓝[Set.range (𝓡∂ (n + 1))] x]
      Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀ :=
    Filter.eventuallyEq_of_mem htarget_nhd (fun y hy => Set.indicator_of_mem hy _)
  exact hfic_rangeI.congr_of_eventuallyEq heq
    (Set.indicator_of_mem htarget _)

-- Direct (leaf-bypass). Witness K := chart-image of `tsupport (g•φ)`.
-- Compact via continuousOn_extChartAt on the compact tsupport; ⊆ target via map_source;
-- tsupport(indicator) ⊆ K by closure_minimal — off K the form vanishes (image_eq_zero_of_notMem_tsupport
-- ⇒ formInCoord = map_zero) so the indicator's support sits inside the closed K.
theorem coord_rep_indicator_tsupport_compact_subset {n : ℕ} {M : Type*} [TopologicalSpace M]
    [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    ∃ K, IsCompact K ∧ K ⊆ (extChartAt (𝓡∂ (n + 1)) c₀).target ∧
      tsupport ((extChartAt (𝓡∂ (n + 1)) c₀).target.indicator
        (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
          (smul_form (𝓡∂ (n + 1)) g hg φ) c₀)) ⊆ K  := by
  set ψ := smul_form (𝓡∂ (n + 1)) g hg φ with hψ
  have hsupp' : tsupport (fun x => ψ x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source := by
    refine Set.Subset.trans ?_ hsupp
    apply closure_mono
    intro x hx
    rw [Function.mem_support] at hx ⊢
    intro hg0
    apply hx
    change g x • φ x = 0
    rw [hg0, zero_smul]
  have h_compact : IsCompact
      (extChartAt (𝓡∂ (n + 1)) c₀ '' tsupport (fun x => ψ x)) := by
    apply ((isClosed_tsupport (fun x => ψ x)).isCompact).image_of_continuousOn
    exact (continuousOn_extChartAt c₀).mono
      (hsupp'.trans (extChartAt_source (𝓡∂ (n + 1)) c₀).symm.subset)
  refine ⟨_, h_compact, ?_, ?_⟩
  · intro y hy
    obtain ⟨x, hx, rfl⟩ := hy
    have hx_source : x ∈ (extChartAt (𝓡∂ (n + 1)) c₀).source := by
      rw [extChartAt_source]; exact hsupp' hx
    exact (extChartAt (𝓡∂ (n + 1)) c₀).map_source hx_source
  · apply closure_minimal _ h_compact.isClosed
    intro y hy
    rw [Function.mem_support] at hy
    by_contra hynot
    apply hy
    by_cases hyt : y ∈ (extChartAt (𝓡∂ (n + 1)) c₀).target
    · rw [Set.indicator_of_mem hyt]
      have hsymm_notmem : (extChartAt (𝓡∂ (n + 1)) c₀).symm y ∉ tsupport (fun x => ψ x) := by
        intro hmem
        apply hynot
        rw [show y = extChartAt (𝓡∂ (n + 1)) c₀ ((extChartAt (𝓡∂ (n + 1)) c₀).symm y) from
          (PartialEquiv.right_inv _ hyt).symm]
        exact Set.mem_image_of_mem _ hmem
      have hψ0 : ψ ((extChartAt (𝓡∂ (n + 1)) c₀).symm y) = 0 :=
        image_eq_zero_of_notMem_tsupport hsymm_notmem
      simp only [Library.Geometry.Manifold.MExtDerivCoord.formInCoord, hψ0, map_zero]
    · exact Set.indicator_of_notMem hyt _

theorem coord_rep_indicator_contdiffon {n : ℕ} {M : Type*} [TopologicalSpace M]
    [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    ContDiffOn ℝ ∞ ((extChartAt (𝓡∂ (n + 1)) c₀).target.indicator
      (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀)) (Set.range (𝓡∂ (n + 1)))  := by
  -- ContDiffOn is local: at each x ∈ range I, split on whether x lies in the chart target.
  -- In-target (hA): indicator = formInCoord, smooth via form_in_coord_smooth, transported to
  --   range I since target ∈ 𝓝[range I] x (extChartAt_target_mem_nhdsWithin_of_mem).
  -- Off-target (hB): given tsupport(indicator) ⊆ target (from the compact-subset sibling),
  --   x ∉ target ⇒ x ∉ tsupport ⇒ indicator ≡ 0 near x ⇒ ContDiffWithinAt 0.
  obtain ⟨K, hKcompact, hKsub, hKtsupp⟩ :=
    coord_rep_indicator_tsupport_compact_subset g hg c₀ hsupp φ
  have htsub : tsupport ((extChartAt (𝓡∂ (n + 1)) c₀).target.indicator
      (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀)) ⊆
      (extChartAt (𝓡∂ (n + 1)) c₀).target := hKtsupp.trans hKsub
  have hA := coord_indicator_contdiffwithinat_at_target_pt g hg c₀ hsupp φ
  have hB := coord_indicator_contdiffwithinat_off_target_pt g hg c₀ hsupp φ htsub
  intro x hx
  by_cases hxt : x ∈ (extChartAt (𝓡∂ (n + 1)) c₀).target
  · exact hA x hx hxt
  · exact hB x hx hxt

theorem coord_halfspace_rep {n : ℕ} {M : Type*} [TopologicalSpace M]
    [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    ∃ w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ,
      ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1))) ∧ HasCompactSupport w ∧
      Set.EqOn w (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀) (extChartAt (𝓡∂ (n + 1)) c₀).target ∧
      tsupport w ⊆ (extChartAt (𝓡∂ (n + 1)) c₀).target  := by
  obtain ⟨K, hKc, hKt, hsub⟩ :=
    coord_rep_indicator_tsupport_compact_subset g hg c₀ hsupp φ
  refine ⟨(extChartAt (𝓡∂ (n + 1)) c₀).target.indicator
      (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀), ?_, ?_, ?_, ?_⟩
  · exact coord_rep_indicator_contdiffon g hg c₀ hsupp φ
  · exact hKc.of_isClosed_subset (isClosed_tsupport _) hsub
  · exact fun y hy => Set.indicator_of_mem hy _
  · exact hsub.trans hKt

-- face_full_integral_eq_target_restrict: shrink full-ℝⁿ face integral of half-space rep `w`
-- to the ∂M chart target using the fact that tsupport w ⊆ ambient target.
-- Key: t ∉ (extChartAt 𝓘 p₀).target ⟹ faceEmbedL t ∉ tsupport w ⟹ integrand = 0.
theorem face_full_integral_eq_target_restrict {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (c₀ : M) (p₀ : Bdry n M) (hcenter : p₀.val = c₀)
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw_ts : tsupport w ⊆ (extChartAt (𝓡∂ (n + 1)) c₀).target) :
    (∫ t : EuclideanSpace ℝ (Fin n),
        w (faceEmbedL t) (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))
          ∂MeasureTheory.volume)
      = ∫ t in (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
          w (faceEmbedL t) (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))
            ∂MeasureTheory.volume := by
  symm
  apply setIntegral_eq_integral_of_forall_compl_eq_zero
  intro t ht
  -- t ∉ (extChartAt 𝓘 p₀).target; need: w (faceEmbedL t) (basis) = 0
  -- Step 1: Unfold the ∂M-model chart target
  -- (extChartAt 𝓘 p₀).target = (chartAt p₀).target via extChartAt_target + modelWithCornersSelf
  have ht_chart : t ∉ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).target := by
    intro hmem
    apply ht
    rw [extChartAt_target (𝓘(ℝ, EuclideanSpace ℝ (Fin n))),
        modelWithCornersSelf_coe_symm, Set.preimage_id,
        modelWithCornersSelf_coe, Set.range_id, Set.inter_univ]
    exact hmem
  -- Step 2: (chartAt p₀).target = chartTarget p₀ by instance definition
  have ht_chartTarget : t ∉ Library.Geometry.ManifoldBoundary.Defs.chartTarget p₀ := by
    exact_mod_cast ht_chart
  -- Step 3: chartTarget p₀ = faceEmbed ⁻¹' (extChartAt (𝓡∂) p₀.val).target
  -- So faceEmbedL t ∉ (extChartAt (𝓡∂) c₀).target
  have hfacemem : faceEmbedL t ∉ (extChartAt (𝓡∂ (n + 1)) c₀).target := by
    intro habs
    apply ht_chartTarget
    rw [Library.Geometry.ManifoldBdry.BdryChart.chartTarget_eq_faceEmbed_preimage p₀]
    simp only [Set.mem_preimage]
    rwa [Library.Geometry.ManifoldBdry.FaceEmbedLemmas.faceEmbed_eq_faceEmbedL, hcenter]
  -- Step 4: faceEmbedL t ∉ tsupport w (since tsupport w ⊆ ambient target)
  have hnotts : faceEmbedL t ∉ tsupport w := fun h => hfacemem (hw_ts h)
  have hnotsup : faceEmbedL t ∉ Function.support w := fun h => hnotts (subset_closure h)
  have hzero : w (faceEmbedL t) = 0 := by
    simp only [Function.mem_support, ne_eq, not_not] at hnotsup
    exact hnotsup
  simp [hzero]

-- face_w_eq_formincoord_target_restrict: swap the half-space rep `w` for `formInCoord` under
-- the target-restricted face integral via setIntegral_congr_fun, using chartTarget membership
-- to show faceEmbedL t lands in the ambient chart target where hw_eq applies.
theorem face_w_eq_formincoord_target_restrict {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M) (hcenter : p₀.val = c₀)
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw_eq : Set.EqOn w (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀) (extChartAt (𝓡∂ (n + 1)) c₀).target) :
    (∫ t in (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
          w (faceEmbedL t) (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))
            ∂MeasureTheory.volume)
      = ∫ t in (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
          Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
            (smul_form (𝓡∂ (n + 1)) g hg φ) c₀ (faceEmbedL t)
            (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))
    := by
  apply MeasureTheory.setIntegral_congr_fun
  · exact (isOpen_extChartAt_target p₀).measurableSet
  · intro t ht
    have ht' : t ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).target := by
      have h := ht
      rw [extChartAt_target, modelWithCornersSelf_coe_symm, Set.preimage_id,
          modelWithCornersSelf_coe, Set.range_id, Set.inter_univ] at h
      exact h
    have hfmem : faceEmbedL t ∈ (extChartAt (𝓡∂ (n + 1)) c₀).target := by
      have htc : t ∈ Library.Geometry.ManifoldBoundary.Defs.chartTarget p₀ := ht'
      have hpre : Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.faceEmbed t ∈
          (extChartAt (𝓡∂ (n + 1)) p₀.val).target := by
        rw [Library.Geometry.ManifoldBdry.BdryChart.chartTarget_eq_faceEmbed_preimage p₀] at htc
        exact htc
      rwa [Library.Geometry.ManifoldBdry.FaceEmbedLemmas.faceEmbed_eq_faceEmbedL,
           hcenter] at hpre
    simp only [hw_eq hfmem]

-- Shrink the full-ℝⁿ face integral of the half-space rep `w` to the ∂M chart target, then
-- swap `w → formInCoord`. The reverse chart-membership that is FALSE for raw formInCoord
-- (`faceEmbedL t ∈ ambient target ⟹ t ∈ ∂M chart target`) IS a theorem for `w` because the
-- boundary chart target = `faceEmbed ⁻¹' (extChartAt (𝓡∂) p₀.val).target`
-- (proved Library `chartTarget_eq_faceEmbed_preimage`), and `tsupport w ⊆` ambient target.
-- Two Builder legs joined by `.trans`:
--   reduce to hA via `face_full_integral_eq_target_restrict` (support of `t ↦ w (faceEmbedL t)`
--     lies in the target, so the full integral restricts to it),
--   then `face_w_eq_formincoord_target_restrict` (hB) swaps `w` for `formInCoord` on the target
--     via `hw_eq`, closing the goal from hA.
-- Never state `∫_ℝⁿ formInCoord = ∫_ℝⁿ w` (dead `face_formincoord_eq_w_rep`); never ask for
-- global `ContDiff w` (Whitney) — all toolkit stays `ContDiffOn (range 𝓡∂)`.
theorem face_w_eq_formincoord_on_target {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M) (hcenter : p₀.val = c₀)
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw_cd : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hw_cs : HasCompactSupport w)
    (hw_eq : Set.EqOn w (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀) (extChartAt (𝓡∂ (n + 1)) c₀).target)
    (hw_ts : tsupport w ⊆ (extChartAt (𝓡∂ (n + 1)) c₀).target) :
    (∫ t : EuclideanSpace ℝ (Fin n),
        w (faceEmbedL t) (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))
          ∂MeasureTheory.volume)
      = ∫ t in (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
          Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
            (smul_form (𝓡∂ (n + 1)) g hg φ) c₀ (faceEmbedL t)
            (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))
            ∂MeasureTheory.volume  := by
  -- Restrict the full-space face integral of `w` to the ∂M chart target (support of
  -- `t ↦ w (faceEmbedL t)` lies in the target, since `tsupport w ⊆` ambient target and
  -- `chartTarget = faceEmbed ⁻¹' ambient target`), then swap `w` for `formInCoord` via `hw_eq`.
  have hA := face_full_integral_eq_target_restrict c₀ p₀ hcenter w hw_ts
  have hB := face_w_eq_formincoord_target_restrict g hg c₀ φ p₀ hcenter w hw_eq
  exact hA.trans hB

-- mside_localcoeff_integral_eq_topcoeff_w_target: integrand rewrite on the chart target,
-- swapping localCoeff(mextDeriv(g•φ)) c₀ to topCoeff(extDerivWithin w (range I)) via
-- form_in_coord_mext_deriv_eq + heqon EqOn-to-EventuallyEq swap under extDerivWithin.
theorem mside_localcoeff_integral_eq_topcoeff_w_target {n : ℕ} {M : Type*} [TopologicalSpace M]
    [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n)
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (heqon : Set.EqOn w (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀) (extChartAt (𝓡∂ (n + 1)) c₀).target)
    (hwtsupp : tsupport w ⊆ (extChartAt (𝓡∂ (n + 1)) c₀).target) :
    (∫ y in (extChartAt (𝓡∂ (n + 1)) c₀).target,
        localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) c₀ y
          ∂MeasureTheory.volume)
      = (∫ y in (extChartAt (𝓡∂ (n + 1)) c₀).target,
          topCoeff (extDerivWithin w (Set.range (𝓡∂ (n + 1))) y) ∂MeasureTheory.volume) := by
  have htmeas : MeasurableSet (extChartAt (𝓡∂ (n + 1)) c₀).target := by
    rw [extChartAt_target]
    exact ((chartAt (EuclideanHalfSpace (n + 1)) c₀).open_target.preimage
      (𝓡∂ (n + 1)).continuous_symm).measurableSet.inter
      (𝓡∂ (n + 1)).isClosed_range.measurableSet
  apply setIntegral_congr_fun htmeas
  intro y hy
  simp only [localCoeff]
  rw [form_in_coord_mext_deriv_eq _ _ c₀ y hy]
  congr 1
  apply Filter.EventuallyEq.extDerivWithin_eq
  · apply Filter.eventually_of_mem (extChartAt_target_mem_nhdsWithin_of_mem hy)
    exact fun z hz => (heqon hz).symm
  · exact (heqon hy).symm

-- topcoeff_extderiv_w_integral_target_eq_halfspace: domain extension target → halfspace;
-- integrand vanishes off tsupport w ⊆ target via extDerivWithin = 0 off tsupport.
theorem topcoeff_extderiv_w_integral_target_eq_halfspace {n : ℕ} {M : Type*} [TopologicalSpace M]
    [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M]
    (c₀ : M)
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (hwtsupp : tsupport w ⊆ (extChartAt (𝓡∂ (n + 1)) c₀).target) :
    (∫ y in (extChartAt (𝓡∂ (n + 1)) c₀).target,
          topCoeff (extDerivWithin w (Set.range (𝓡∂ (n + 1))) y) ∂MeasureTheory.volume)
      = (∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
          topCoeff (extDerivWithin w (Set.range (𝓡∂ (n + 1))) y) ∂MeasureTheory.volume) := by
  symm
  apply setIntegral_eq_of_subset_of_forall_diff_eq_zero
  · apply measurableSet_le measurable_const
    exact (measurable_pi_apply 0).comp (@WithLp.measurable_ofLp 2 _ _)
  · intro y hy
    have hmem : y ∈ Set.range (𝓡∂ (n + 1)) := extChartAt_target_subset_range c₀ hy
    rw [range_modelWithCornersEuclideanHalfSpace] at hmem
    exact hmem
  · intro y hy
    have hnotsupp : y ∉ tsupport w := fun h => hy.2 (hwtsupp h)
    have hw_eq : w =ᶠ[nhds y] 0 := notMem_tsupport_iff_eventuallyEq.mp hnotsupp
    have hzero : extDerivWithin w (Set.range (𝓡∂ (n + 1))) y = 0 := by
      rw [hw_eq.extDerivWithin_eq_nhds]
      simp only [extDerivWithin, Pi.zero_def, fderivWithin_fun_const]
      exact (ContinuousAlternatingMap.alternatizeUncurryFinCLM ℝ _ ℝ).map_zero
    simp [topCoeff, hzero]

-- M-side coord brick: ∫_target localCoeff(d(g•φ)) = ∫_{y₀≥0} topCoeff(extDerivWithin w).
-- h1 rewrites the integrand on the chart target (form_in_coord_mext_deriv_eq + heqon swap to w);
-- h2 extends the domain target → {y₀≥0} since extDerivWithin w vanishes off tsupport w ⊆ target.
theorem mside_localcoeff_integral_eq_topcoeff_on {n : ℕ} {M : Type*} [TopologicalSpace M]
    [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n)
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (hw : ContDiffOn ℝ ∞ w (Set.range (𝓡∂ (n + 1)))) (hwsupp : HasCompactSupport w)
    (heqon : Set.EqOn w (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ) c₀) (extChartAt (𝓡∂ (n + 1)) c₀).target)
    (hwtsupp : tsupport w ⊆ (extChartAt (𝓡∂ (n + 1)) c₀).target) :
    (∫ y in (extChartAt (𝓡∂ (n + 1)) c₀).target,
        localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) c₀ y
          ∂MeasureTheory.volume)
      = (∫ y in {y : EuclideanSpace ℝ (Fin (n + 1)) | 0 ≤ y 0},
          topCoeff (extDerivWithin w (Set.range (𝓡∂ (n + 1))) y) ∂MeasureTheory.volume)  := by
  have h1 := mside_localcoeff_integral_eq_topcoeff_w_target
    g hg c₀ hsupp φ w hw hwsupp heqon hwtsupp
  have h2 := topcoeff_extderiv_w_integral_target_eq_halfspace c₀ w hw hwsupp hwtsupp
  exact h1.trans h2

-- M-side coordinate brick with the face pivot ranging over the ∂M chart TARGET.
-- Reuse the half-space-smooth coordinate rep `w` (ContDiffOn (range 𝓡∂), never global —
-- Whitney is unavoidable globally), then the SAME divergence/FTC toolkit as the dead-ℝⁿ
-- twin: coord_halfspace_rep ⟶ mside_localcoeff_integral_eq_topcoeff_on (h1, LHS = ∫_{y₀≥0}
-- topCoeff(extDerivWithin w)) ⟶ halfspace_topcoeff_extderiv_eq_neg_face_on (h2, = −∫_ℝⁿ
-- w(faceEmbedL t)). The only NEW content vs the ℝⁿ-pivot brick is the final bridge h3
-- (face_w_eq_formincoord_on_target): shrink ∫_ℝⁿ w(faceEmbedL t) to ∫_target via
-- tsupport w ⊆ target (true only for w), then swap w → formInCoord by EqOn on target.
-- NEVER state ∫_ℝⁿ formInCoord = ∫_ℝⁿ w (the dead face_formincoord_eq_w_rep).
-- Combine by `rw [h1, h2, h3]`.
theorem mside_chart_density_localcoeff_eq_neg_face_pivot_on_target {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M) (hcenter : p₀.val = c₀) :
    ∫ y in (extChartAt (𝓡∂ (n + 1)) c₀).target,
        localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) c₀ y ∂MeasureTheory.volume
      = - ∫ t in (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
          Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
            (smul_form (𝓡∂ (n + 1)) g hg φ) c₀ (faceEmbedL t)
            (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)) ∂MeasureTheory.volume  := by
  obtain ⟨w, hw_cd, hw_cs, hw_eq, hw_ts⟩ := coord_halfspace_rep g hg c₀ hsupp φ
  have h1 := mside_localcoeff_integral_eq_topcoeff_on g hg c₀ hsupp φ w hw_cd hw_cs hw_eq hw_ts
  have h2 := halfspace_topcoeff_extderiv_eq_neg_face_on w hw_cd hw_cs
  have h3 := face_w_eq_formincoord_on_target g hg c₀ hsupp φ p₀ hcenter w hw_cd hw_cs hw_eq hw_ts
  rw [h1, h2, h3]

-- sum_smul_eq_pos_smul: weighted sum (nonneg weights summing to 1, each nonzero-weight term a pos
-- scalar multiple of v) equals a positive scalar multiple of v
theorem sum_smul_eq_pos_smul {ι : Type*} {V : Type*} [AddCommGroup V] [Module ℝ V]
    (s : Finset ι) (w : ι → ℝ) (g : ι → V) (v : V)
    (hw0 : ∀ i, 0 ≤ w i) (hsum : ∑ i ∈ s, w i = 1)
    (hray : ∀ i, w i ≠ 0 → ∃ c : ℝ, 0 < c ∧ g i = c • v) :
    ∃ c : ℝ, 0 < c ∧ ∑ i ∈ s, w i • g i = c • v := by
  classical
  let C : ι → ℝ := fun i =>
    if h : w i = 0 then 0 else (hray i h).choose
  have hC_pos : ∀ i, w i ≠ 0 → 0 < C i := by
    intro i hi
    simp only [C, hi, dite_false]
    exact ((hray i hi).choose_spec).1
  have hC_eq : ∀ i, w i ≠ 0 → g i = C i • v := by
    intro i hi
    simp only [C, hi, dite_false]
    exact ((hray i hi).choose_spec).2
  have hC_nonneg : ∀ i, 0 ≤ C i := by
    intro i
    by_cases hi : w i = 0
    · simp [C, hi]
    · exact le_of_lt (hC_pos i hi)
  refine ⟨∑ i ∈ s, w i * C i, ?_, ?_⟩
  · rw [Finset.sum_pos_iff_of_nonneg (fun i _ => mul_nonneg (hw0 i) (hC_nonneg i))]
    have hpos_sum : 0 < ∑ i ∈ s, w i := by linarith [hsum.symm ▸ zero_lt_one]
    rw [Finset.sum_pos_iff_of_nonneg (fun i _ => hw0 i)] at hpos_sum
    obtain ⟨i₀, hi₀s, hi₀w⟩ := hpos_sum
    exact ⟨i₀, hi₀s, mul_pos hi₀w (hC_pos i₀ (ne_of_gt hi₀w))⟩
  · have heq : ∑ i ∈ s, w i • g i = ∑ i ∈ s, (w i * C i) • v := by
      apply Finset.sum_congr rfl
      intro i _
      by_cases hi : w i = 0
      · simp [hi]
      · rw [hC_eq i hi, smul_smul]
    rw [heq, ← Finset.sum_smul]

theorem inducedorientfun_collapse_to_anchor {n : ℕ} {M : Type*}
    [TopologicalSpace M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (p' : Bdry n M) :
    ∃ c : ℝ, 0 < c ∧
      Library.Geometry.Manifold.InducedOrientDefs.inducedOrientFun p'
        = c • Library.Geometry.Manifold.InducedOrientDefs.inducedOrientChartFun p' p'  := by
  have heq : inducedOrientFun p' = ∑ q ∈ (inducedOrientPOU n M).finsupport p',
      inducedOrientPOU n M q p' • inducedOrientChartFun q p' :=
    ((inducedOrientPOU n M).sum_finsupport_smul_eq_finsum p'
      (fun q _ => inducedOrientChartFun q p')).symm
  have hray : ∀ q : Bdry n M, inducedOrientPOU n M q p' ≠ 0 →
      ∃ c : ℝ, 0 < c ∧ inducedOrientChartFun q p' = c • inducedOrientChartFun p' p' :=
    fun q hq => inducedOrientChartFun_eq_pos_smul_self q p'
      (mem_chartAt_source_of_inducedOrientPOU_ne_zero q p' hq)
  obtain ⟨c, hc, hceq⟩ := sum_smul_eq_pos_smul
      ((inducedOrientPOU n M).finsupport p')
      (fun q => inducedOrientPOU n M q p')
      (fun q => inducedOrientChartFun q p')
      (inducedOrientChartFun p' p')
      (fun q => (inducedOrientPOU n M).nonneg q p')
      ((inducedOrientPOU n M).sum_finsupport p' (Set.mem_univ p')) hray
  exact ⟨c, hc, heq.trans hceq⟩

theorem inducedorientfun_eq_pos_smul_chartfun {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (p₀ : Bdry n M)
    (y : EuclideanSpace ℝ (Fin n))
    (hy : y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target) :
    ∃ c : ℝ, 0 < c ∧
      Library.Geometry.Manifold.InducedOrientDefs.inducedOrientFun
          ((extChartAt (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p₀).symm y)
        = c • Library.Geometry.Manifold.InducedOrientDefs.inducedOrientChartFun p₀
          ((extChartAt (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p₀).symm y)  := by
  set p' := (extChartAt (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p₀).symm y with hp'
  have hmem : p' ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source := by
    rw [hp', ← extChartAt_source (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p₀]
    exact (extChartAt (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p₀).map_target hy
  obtain ⟨c₁, hc₁, hA⟩ :=
    Library.Geometry.Manifold.InducedOrientNonzero.inducedOrientChartFun_eq_pos_smul_self p₀ p' hmem
  obtain ⟨c₂, hc₂, hB⟩ := inducedorientfun_collapse_to_anchor p'

  refine ⟨c₂ / c₁, div_pos hc₂ hc₁, ?_⟩
  rw [hB, hA, smul_smul, div_mul_cancel₀ _ (ne_of_gt hc₁)]

-- Boundary refForm curried-face readout, leaf-bypass (all cites proved).
-- continuousLinearMapAt ∘ symmL round-trip (chartfun_triv_read +
--   continuousLinearMapAt_apply_of_mem, needs symm y ∈ chart source = baseSet) exposes the
--   formInCoord readout at p₀.val on the ambient chart point; chart-compat
--   (bdry_val_rep_eq_faceembed + faceEmbed_eq_faceEmbedL) rewrites that point to faceEmbedL y,
--   then hcenter swaps p₀.val → c₀ to land on the target.

theorem chartfun_clm_readout_eq_curried_face {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (c₀ : M) (p₀ : Bdry n M) (hcenter : p₀.val = c₀)
    (y : EuclideanSpace ℝ (Fin n))
    (hy : y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target) :
    Trivialization.continuousLinearMapAt ℝ
        (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
          (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p₀)
        ((extChartAt (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p₀).symm y)
        (Library.Geometry.Manifold.InducedOrientDefs.inducedOrientChartFun p₀
          ((extChartAt (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p₀).symm y))
      = ContinuousAlternatingMap.compContinuousLinearMapCLM (faceEmbedL (n := n))
          ((Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
              (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) c₀
              (faceEmbedL y)).curryLeft
            (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)) := by
  have hsource : (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y ∈
      (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source := by
    rw [← extChartAt_source 𝓘(ℝ, EuclideanSpace ℝ (Fin n))]
    exact (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).map_target hy
  have hcompat : extChartAt (𝓡∂ (n + 1)) p₀.val
      ((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y).val = faceEmbedL y := by
    have hyt : y ∈ Library.Geometry.ManifoldBoundary.Defs.chartTarget p₀ := by
      simpa using hy
    rw [Library.Geometry.ManifoldBdry.BdryValSmooth.bdry_val_rep_eq_faceembed p₀ y hyt,
        Library.Geometry.ManifoldBdry.FaceEmbedLemmas.faceEmbed_eq_faceEmbedL]
  rw [Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ hsource,
      Library.Geometry.Manifold.InducedOrientSmooth.chartfun_triv_read p₀ _ hsource,
      hcompat, hcenter]

-- topcoeff_compface_curryneg_eq_neg_topcoeff: topCoeff of curried-face form with -e₀ equals
-- -topCoeff β, by curry_face_apply_basis from Library.Geometry.Manifold.FaceEmbedAlts.
theorem topcoeff_compface_curryneg_eq_neg_topcoeff {n : ℕ}
    (β : EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin (n + 1)]→L[ℝ] ℝ) :
    topCoeff (ContinuousAlternatingMap.compContinuousLinearMapCLM (faceEmbedL (n := n))
        (β.curryLeft (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)))
      = - topCoeff β := by
  simp only [topCoeff]
  exact Library.Geometry.Manifold.FaceEmbedAlts.curry_face_apply_basis β

-- real_sign_neg_pos_mul: sign(-(c*z)) = -sign(z) for c > 0, via sign_neg + pos-scale preserves sign
theorem real_sign_neg_pos_mul (c z : ℝ) (hc : 0 < c) :
    Real.sign (-(c * z)) = - Real.sign z := by
  rw [Real.sign_neg]
  congr 1
  rcases lt_trichotomy z 0 with hn | rfl | hp
  · exact (Real.sign_of_neg (mul_neg_of_pos_of_neg hc hn)).trans (Real.sign_of_neg hn).symm
  · simp
  · exact (Real.sign_of_pos (mul_pos hc hp)).trans (Real.sign_of_pos hp).symm

-- formincoord_smul_form_factor: formInCoord factors g through smul_form via CLM linearity
-- Unfolds formInCoord and smul_form (rfl), applies map_smul (CLM linearity in fiber), then
-- closes (c • f) v = c • f v via ContinuousAlternatingMap.smul_apply.
theorem formincoord_smul_form_factor
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (g : M → ℝ) (hg : ContMDiff I 𝓘(ℝ, ℝ) ∞ g)
    (φ : DiffForm I M k) (x : M) (z : E) (v : Fin k → E) :
    Library.Geometry.Manifold.MExtDerivCoord.formInCoord I (smul_form I g hg φ) x z v
      = g ((extChartAt I x).symm z) •
        Library.Geometry.Manifold.MExtDerivCoord.formInCoord I φ x z v := by
  simp only [Library.Geometry.Manifold.MExtDerivCoord.formInCoord]
  have h : (smul_form I g hg φ) ((extChartAt I x).symm z) =
      g ((extChartAt I x).symm z) • φ ((extChartAt I x).symm z) := rfl
  rw [h]
  simp only [map_smul]
  simp [ContinuousAlternatingMap.smul_apply]

-- chart_symm_extchart_val_pin: left_inv of ambient extChartAt applied to a boundary-chart
-- preimage point; membership in ambient source follows from boundary chart source definition.
theorem chart_symm_extchart_val_pin {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M] [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (p₀ : Bdry n M) (y : EuclideanSpace ℝ (Fin n))
    (hy : y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target) :
    (extChartAt (𝓡∂ (n + 1)) p₀.val).symm
        (extChartAt (𝓡∂ (n + 1)) p₀.val
          (((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y).val))
      = ((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y).val := by
      apply (extChartAt (𝓡∂ (n + 1)) p₀.val).left_inv
      have hq := (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).map_target hy
      rw [extChartAt_source] at hq
      exact hq

-- face_embedl_eq_extchart_val: faceEmbedL y equals the ambient extended chart at c₀
-- applied to the boundary point (extChartAt 𝓘 p₀).symm y, using extChartAt_val_eq_faceEmbed_chartAt
-- (which relates the ambient chart at p₀.val to faceEmbed ∘ chartAt) and faceEmbed_eq_faceEmbedL.
theorem face_embedl_eq_extchart_val {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [T2Space (Bdry n M)]
    (c₀ : M) (p₀ : Bdry n M) (hcenter : p₀.val = c₀)
    (y : EuclideanSpace ℝ (Fin n))
    (hy : y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target) :
    faceEmbedL y
      = extChartAt (𝓡∂ (n + 1)) c₀
          (((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y).val) := by
  rw [← hcenter]
  set p := (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y
  have hp_src : p ∈ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source := by
    simpa only [extChartAt_source] using
      (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).map_target hy
  have hchart : chartAt (EuclideanSpace ℝ (Fin n)) p₀ p = y := by
    have h := (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).right_inv hy
    simp only [extChartAt_coe, extChartAt_coe_symm, modelWithCornersSelf_coe,
      modelWithCornersSelf_coe_symm, Function.comp_id, Function.id_comp] at h
    exact h
  have key := extChartAt_val_eq_faceEmbed_chartAt p₀ p hp_src
  rw [hchart] at key
  rw [← faceEmbed_eq_faceEmbedL]
  exact key.symm

-- Leaf-bypass: contrapositive support-localization of the M-side density.
-- If y ∉ extChartAt c₀ '' tsupport g then (extChartAt c₀).symm y ∉ tsupport g
-- (right_inv on target), hence ∉ tsupport (g•φ) (tsupport_smul_subset_left), so
-- mextDeriv (g•φ) vanishes there (mextderiv_vanish_off_tsupport) and the localCoeff
-- reads off a zero form value.
theorem mdensity_nonzero_in_gsupp_image {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) c₀).target,
      localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) c₀ y ≠ 0 →
      y ∈ ⇑(extChartAt (𝓡∂ (n + 1)) c₀) '' tsupport (fun x => g x)  := by
  intro y hy hne
  by_contra hynot
  apply hne
  -- the chart-symm preimage of y falls outside tsupport g
  have h_notmem : (extChartAt (𝓡∂ (n + 1)) c₀).symm y ∉ tsupport (fun x => g x) := by
    intro hmem
    apply hynot
    rw [show y = extChartAt (𝓡∂ (n + 1)) c₀ ((extChartAt (𝓡∂ (n + 1)) c₀).symm y) from
      (PartialEquiv.right_inv _ hy).symm]
    exact Set.mem_image_of_mem _ hmem
  -- g•φ is supported in tsupport g, so the preimage is outside its tsupport too
  have h_notmem2 : (extChartAt (𝓡∂ (n + 1)) c₀).symm y ∉
      tsupport (fun x => (smul_form (𝓡∂ (n + 1)) g hg φ) x) :=
    fun hmem => h_notmem (tsupport_smul_subset_left (fun x => g x) (fun x => φ x) hmem)
  -- off the form's support, mextDeriv vanishes pointwise
  have h_w : mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)
      ((extChartAt (𝓡∂ (n + 1)) c₀).symm y) = 0 :=
    mextderiv_vanish_off_tsupport (𝓡∂ (n + 1))
      (smul_form (𝓡∂ (n + 1)) g hg φ) _ h_notmem2
  -- hence the localCoeff reads off a zero form value
  simp only [localCoeff, topCoeff, formInCoord, h_w, map_zero]
  simp

-- face_embedl_zeroth_coord: faceEmbedL lands on {y0 = 0}; all basis vectors in the sum
-- have succ index ≥ 1, so the zeroth component vanishes by EuclideanSpace.basisFun_apply
-- and Fin.succ_ne_zero.
theorem face_embedl_zeroth_coord {n : ℕ} :
    ∀ t : EuclideanSpace ℝ (Fin n), (faceEmbedL t) 0 = 0 := by
  intro t
  simp [faceEmbedL, EuclideanSpace.basisFun_apply, Fin.succ_ne_zero]

-- smul_form_support_misses_bdry: interior bump support misses every boundary point,
-- so the PoU-weighted form's pointwise function vanishes on all of ∂M.
-- Uses disjoint_interior_boundary + support_toSmoothPartitionOfUnity_subset.
theorem smul_form_support_misses_bdry {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (i : ιM)
    (hsupp : tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M) :
    ∀ p : Bdry n M, p.val ∉ Function.support (fun x =>
      (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)

        (B.toSmoothPartitionOfUnity i).contMDiff φ) x) := by
  intro p
  simp only [Function.mem_support, not_ne_iff]
  have hpbdry : p.val ∈ (𝓡∂ (n + 1)).boundary M := p.prop
  have hpnint : p.val ∉ (𝓡∂ (n + 1)).interior M :=
    Set.disjoint_right.mp ModelWithCorners.disjoint_interior_boundary hpbdry
  have hpnsupp : p.val ∉ tsupport (B i) := fun h => hpnint (hsupp h)
  have hPoUzero : B.toSmoothPartitionOfUnity i p.val = 0 := by
    by_contra h
    exact hpnsupp (subset_tsupport _ (B.support_toSmoothPartitionOfUnity_subset i
      (Function.mem_support.mpr h)))
  change B.toSmoothPartitionOfUnity i p.val • φ p.val = 0
  rw [hPoUzero, zero_smul]

-- leaf-bypass: face point z (z 0 = 0, z ∈ target) ⟹ chart preimage is a ∂M point
-- (frontier_range_modelWithCornersEuclideanHalfSpace + symm_mem_boundary_of_frontier),
-- where the interior-supported PoU-weighted form vanishes (smul_form_support_misses_bdry),
-- so formInCoord = continuousLinearMapAt _ 0 = 0 (map_zero).
theorem formincoord_smul_clm_zero_on_face {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (i : ιM)
    (hsupp : tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M) :
    ∀ z : EuclideanSpace ℝ (Fin (n + 1)),
      z ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target → z 0 = 0 →
      Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ) (B.c i) z = 0  := by
  intro z hz hz0
  haveI : NeZero (n + 1) := ⟨Nat.succ_ne_zero n⟩
  have hfr : z ∈ frontier (Set.range (𝓡∂ (n + 1))) := by
    rw [frontier_range_modelWithCornersEuclideanHalfSpace]
    exact hz0.symm
  have hbdry : (extChartAt (𝓡∂ (n + 1)) (B.c i)).symm z ∈ (𝓡∂ (n + 1)).boundary M :=
    Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.symm_mem_boundary_of_frontier
      (B.c i) z hz hfr
  have hval : smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff φ
      ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm z) = 0 :=
    Function.notMem_support.mp
      (smul_form_support_misses_bdry B φ i hsupp
        ⟨(extChartAt (𝓡∂ (n + 1)) (B.c i)).symm z, hbdry⟩)
  simp only [Library.Geometry.Manifold.MExtDerivCoord.formInCoord]
  rw [hval]
  exact map_zero _

theorem w_vanishes_on_zeroth_coord {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (hB : B.IsSubordinate (fun x => (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (i : ιM)
    (hsupp : tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M)
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (heqon : Set.EqOn w (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ) (B.c i))
        (extChartAt (𝓡∂ (n + 1)) (B.c i)).target)
    (hwtsupp : tsupport w ⊆ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target) :
    ∀ y : EuclideanSpace ℝ (Fin (n + 1)), y 0 = 0 → w y = 0  := by
  have h_face := formincoord_smul_clm_zero_on_face B φ i hsupp
  intro y hy0
  by_cases hmem : y ∈ tsupport w
  · have ht : y ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target := hwtsupp hmem
    rw [heqon ht]
    exact h_face y ht hy0
  · exact image_eq_zero_of_notMem_tsupport hmem

-- Reduce `w (faceEmbedL t) = 0` to two orthogonal facts:
--   h_face0 (face_embedl_zeroth_coord): faceEmbedL lands on {y0 = 0} (pure geometry);
--   h_w_face (w_vanishes_on_zeroth_coord): w (= formInCoord of the interior-supported
--     PoU-weighted form on target, tsupport w ⊆ target) vanishes on the face hyperplane {y0=0}.
-- Compose: w (faceEmbedL t) = 0 since (faceEmbedL t) 0 = 0.
theorem mside_w_vanishes_on_face {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (hB : B.IsSubordinate (fun x => (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (i : ιM)
    (hsupp : tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M)
    (w : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin n]→L[ℝ] ℝ)
    (heqon : Set.EqOn w (Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ) (B.c i))
        (extChartAt (𝓡∂ (n + 1)) (B.c i)).target)
    (hwtsupp : tsupport w ⊆ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target) :
    ∀ t : EuclideanSpace ℝ (Fin n), w (faceEmbedL t) = 0  := by
  have h_face0 := face_embedl_zeroth_coord (n := n)
  have h_w_face := w_vanishes_on_zeroth_coord B hB φ i hsupp w heqon hwtsupp
  intro t
  exact h_w_face (faceEmbedL t) (h_face0 t)


theorem mside_unsigned_target_integral_zero_interior {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (hB : B.IsSubordinate (fun x => (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (i : ιM)
    (hsupp : tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M) :
    (∫ y in (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
        localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1))
          (B.toSmoothPartitionOfUnity i) (B.toSmoothPartitionOfUnity i).contMDiff φ))
          (B.c i) y ∂MeasureTheory.volume) = 0  := by
  set g := B.toSmoothPartitionOfUnity i with hg_def
  set c₀ := B.c i with hc_def
  have hsupp_chart : tsupport (fun x => g x) ⊆
      (chartAt (EuclideanHalfSpace (n + 1)) c₀).source :=
    (closure_mono (B.support_toSmoothPartitionOfUnity_subset i)).trans (hB i)
  obtain ⟨w, hw, hwsupp, heqon, hwtsupp⟩ :=
    coord_halfspace_rep g g.contMDiff c₀ hsupp_chart φ
  rw [mside_localcoeff_integral_eq_topcoeff_on g g.contMDiff c₀ hsupp_chart φ
      w hw hwsupp heqon hwtsupp,
    halfspace_topcoeff_extderiv_eq_neg_face_on w hw hwsupp]
  have hzero := mside_w_vanishes_on_face B hB φ i hsupp w heqon hwtsupp
  have hint : (∫ t : EuclideanSpace ℝ (Fin n),
      w (faceEmbedL t) (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ))
        ∂MeasureTheory.volume) = 0 := by
    simp_rw [hzero]; simp
  rw [hint, neg_zero]

-- `tsupport (B i)` is preconnected: it is the closure of `support (B i)`, which by
-- `support_eq_symm_image` is the continuous image (`extChartAt.symm`) of the convex set
-- `ball ∩ range (𝓡∂)` (ball convex; `range (𝓡∂) = {0 ≤ y 0}` a convex half-space).
theorem bump_tsupport_preconnected {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ) (i : ιM) :
    IsPreconnected (tsupport (B i))  := by
  rw [tsupport]
  refine IsPreconnected.closure ?_
  rw [SmoothBumpFunction.support_eq_symm_image]
  refine IsPreconnected.image ?_ _ ?_
  · refine Convex.isPreconnected ?_
    refine Convex.inter (convex_ball _ _) ?_
    rw [range_modelWithCornersEuclideanHalfSpace]
    exact convex_halfSpace_ge ⟨fun _ _ => rfl, fun _ _ => rfl⟩ 0
  · refine (continuousOn_extChartAt_symm _).mono ?_
    refine subset_trans (Set.inter_subset_inter_left _ Metric.ball_subset_closedBall) ?_
    exact (B i).closedBall_subset

-- Leaf-bypass (M-side of proved `sign_weighted_factor_antimatch_gen`, p₀-free):
-- factor the constant orientation sign ε out via `sign_const_factor_localcoeff`, the
-- sign being constant on the preconnected image `Simg := extChartAt c₀ '' tsupport (B i)`
-- (bump support preconnected, ⊇ PoU support) by `sign_localcoeff_refform_const_on_preconnected`;
-- the density's nonzero set lands in `Simg` via `mdensity_nonzero_in_gsupp_image` + image-monotone.

theorem mside_sign_factor_interior {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (hB : B.IsSubordinate (fun x => (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (i : ιM)
    (hsupp : tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M) :
    ∃ eps : ℝ,
      (∫ y in (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
          Real.sign (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) (B.c i) y)
            * localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1))
              (B.toSmoothPartitionOfUnity i) (B.toSmoothPartitionOfUnity i).contMDiff φ))
              (B.c i) y ∂MeasureTheory.volume)
        = eps • (∫ y in (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
            localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1))
              (B.toSmoothPartitionOfUnity i) (B.toSmoothPartitionOfUnity i).contMDiff φ))
              (B.c i) y ∂MeasureTheory.volume)  := by
  set c₀ := B.c i with hc₀
  have hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ (fun x => (B.toSmoothPartitionOfUnity i) x) :=
    (B.toSmoothPartitionOfUnity i).contMDiff
  have htsS : tsupport (fun x => (B.toSmoothPartitionOfUnity i) x) ⊆ tsupport (B i) :=
    closure_mono (B.support_toSmoothPartitionOfUnity_subset i)
  have hsuppc : tsupport (fun x => (B.toSmoothPartitionOfUnity i) x) ⊆
      (chartAt (EuclideanHalfSpace (n + 1)) c₀).source := htsS.trans (hB i)
  set Simg : Set (EuclideanSpace ℝ (Fin (n + 1))) :=
    ⇑(extChartAt (𝓡∂ (n + 1)) c₀) '' tsupport (B i) with hSimg
  have hSsrc : tsupport (B i) ⊆ (extChartAt (𝓡∂ (n + 1)) c₀).source := by
    rw [extChartAt_source]; exact hB i
  have h1 : IsPreconnected Simg :=
    (bump_tsupport_preconnected B i).image _ ((continuousOn_extChartAt c₀).mono hSsrc)
  have h2 : Simg ⊆ (extChartAt (𝓡∂ (n + 1)) c₀).target := by
    intro y hy; obtain ⟨x, hx, rfl⟩ := hy
    exact (extChartAt (𝓡∂ (n + 1)) c₀).map_source (hSsrc hx)
  have hmono : ⇑(extChartAt (𝓡∂ (n + 1)) c₀) ''
      tsupport (fun x => (B.toSmoothPartitionOfUnity i) x) ⊆ Simg := Set.image_mono htsS
  have h3 : ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) c₀).target,
      localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1))
        (B.toSmoothPartitionOfUnity i) hg φ)) c₀ y ≠ 0 → y ∈ Simg :=
    fun y hy hne => hmono
      (mdensity_nonzero_in_gsupp_image _ hg c₀ hsuppc φ y hy hne)
  obtain ⟨epsM, hpm, hM⟩ :=
    sign_localcoeff_refform_const_on_preconnected (I := 𝓡∂ (n + 1)) (N := M) c₀ Simg h1 h2
  exact ⟨epsM, sign_const_factor_localcoeff _ c₀ epsM (fun y hy hne => hM y (h3 y hy hne))⟩

-- Interior M-side target integral vanishing: factor the constant orientation sign out
-- (`mside_sign_factor_interior`: `∫ sign·localCoeff = eps • ∫ localCoeff`, sign const on the
-- preconnected bump-support image), then the unsigned coordinate integral vanishes
-- (`mside_unsigned_target_integral_zero_interior`: half-space FTC ⇒ a `-`face term that is `0`
-- because the interior support's chart image misses the boundary face `{y0 = 0}`); `eps • 0 = 0`.
theorem mside_coord_target_integral_zero_interior {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (hB : B.IsSubordinate (fun x => (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (i : ιM)
    (hsupp : tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M) :
    (∫ y in (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
        Real.sign (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) (B.c i) y)
          * localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1))
            (B.toSmoothPartitionOfUnity i) (B.toSmoothPartitionOfUnity i).contMDiff φ))
            (B.c i) y
        ∂MeasureTheory.volume) = 0  := by
  have h_factor := mside_sign_factor_interior B hB φ i hsupp
  have h_unsigned := mside_unsigned_target_integral_zero_interior B hB φ i hsupp
  obtain ⟨eps, he⟩ := h_factor
  rw [he, h_unsigned, smul_zero]

-- Interior M-side vanishing: collapse the M-integral of `mextDeriv (PoUᵢ•φ)` to its single
-- chart `c₀ = B.c i` coordinate density via the PROVED `integral_single_chart_collapse`
-- (s12022; support-localization `h_md` from `mextderiv_smul_tsupport_subset` + PoU⊆bump⊆source),
-- then the resulting target integral of `sign(refForm)·localCoeff(mextDeriv …)` is `0`
-- (`mside_coord_target_integral_zero_interior`): the half-space FTC turns it into a `-`face term
-- over the ambient face slice, which vanishes because the form sits in the interior so its
-- coordinate density is `0` on the boundary face `{y0 = 0}`.
theorem mside_interior_integral_zero_hsupp {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (hB : B.IsSubordinate (fun x => (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (i : ιM)
    (hsupp : tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M) :
    DiffForm.integral (mextDeriv (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ)) = 0  := by
  have hsupp_g : tsupport (fun x => (B.toSmoothPartitionOfUnity i) x)
      ⊆ (chartAt (EuclideanHalfSpace (n + 1)) (B.c i)).source :=
    (closure_mono (B.support_toSmoothPartitionOfUnity_subset i)).trans (hB i)
  have h_md : tsupport (fun x => (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1))
        (B.toSmoothPartitionOfUnity i) (B.toSmoothPartitionOfUnity i).contMDiff φ)) x)
      ⊆ (chartAt (EuclideanHalfSpace (n + 1)) (B.c i)).source :=
    mextderiv_smul_tsupport_subset (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff (B.c i) hsupp_g φ
  have h_collapse := integral_single_chart_collapse
    (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1))
      (B.toSmoothPartitionOfUnity i) (B.toSmoothPartitionOfUnity i).contMDiff φ))
    (B.c i) h_md
  have h_coord :
      (∫ y in (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
          Real.sign (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) (B.c i) y)
            * localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1))
              (B.toSmoothPartitionOfUnity i) (B.toSmoothPartitionOfUnity i).contMDiff φ))
              (B.c i) y
          ∂MeasureTheory.volume) = 0 :=
    mside_coord_target_integral_zero_interior B hB φ i hsupp
  rw [← h_collapse]
  exact h_coord

-- Direct construction (leaf-bypass): refine the chart-source open cover to
-- `U x = chart.source ∩ interior M` at interior points (`= chart.source` on ∂M),
-- apply `SmoothBumpCovering.exists_isSubordinate` over `Set.univ` (nhds from
-- `isOpen_interior` + open chart source), then reindex the resulting covering to
-- `Fin (card ι)` (finite by `B.fintype`, compact M) to land the index in `Type 0`.
-- Subordinacy to chart sources is `U x ⊆ chart.source`; the interior clause is
-- `x ∉ boundary ⇒ x ∈ interior ⇒ U x ⊆ interior` (`compl_boundary`).
theorem exists_boundary_centered_bump_covering {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [CompactSpace M] :
    ∃ (ι : Type) (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) M Set.univ),
      B.IsSubordinate (fun x => (chartAt (EuclideanHalfSpace (n + 1)) x).source) ∧
      ∀ i, B.c i ∉ (𝓡∂ (n + 1)).boundary M →
        tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M  := by
  classical
  set I := 𝓡∂ (n + 1) with hI
  have hopen_int : IsOpen (I.interior M) :=
    I.isOpen_interior (n := (∞ : WithTop ℕ∞)) (by simp)
  set U : M → Set M := fun x =>
    if x ∈ I.interior M then (chartAt (EuclideanHalfSpace (n + 1)) x).source ∩ I.interior M
    else (chartAt (EuclideanHalfSpace (n + 1)) x).source with hU
  have hUsub : ∀ x, U x ⊆ (chartAt (EuclideanHalfSpace (n + 1)) x).source := by
    intro x
    simp only [hU]
    split
    · exact Set.inter_subset_left
    · exact subset_rfl
  have hUint : ∀ x, x ∈ I.interior M → U x ⊆ I.interior M := by
    intro x hx
    simp only [hU, if_pos hx]
    exact Set.inter_subset_right
  have hnhds : ∀ x ∈ (Set.univ : Set M), U x ∈ nhds x := by
    intro x _
    simp only [hU]
    split
    · rename_i hx
      exact Filter.inter_mem ((chartAt _ x).open_source.mem_nhds (mem_chart_source _ x))
        (hopen_int.mem_nhds hx)
    · exact (chartAt _ x).open_source.mem_nhds (mem_chart_source _ x)
  obtain ⟨ι, B, hsub⟩ := SmoothBumpCovering.exists_isSubordinate I isClosed_univ hnhds
  haveI : Fintype ι := B.fintype
  let e : ι ≃ Fin (Fintype.card ι) := Fintype.equivFin ι
  refine ⟨Fin (Fintype.card ι), ⟨fun i => B.c (e.symm i), fun i => B.toFun (e.symm i),
    fun i => B.c_mem' (e.symm i), B.locallyFinite.comp_injective e.symm.injective,
    fun x hx => ?_⟩, ?_, ?_⟩
  · obtain ⟨j, hj⟩ := B.eventuallyEq_one' x hx
    refine ⟨e j, ?_⟩
    change ⇑(B.toFun (e.symm (e j))) =ᶠ[nhds x] 1
    rw [Equiv.symm_apply_apply]
    exact hj
  · intro i
    exact (hsub (e.symm i)).trans (hUsub _)
  · intro i hi
    have hmem : B.c (e.symm i) ∈ I.interior M := by
      rw [← I.compl_boundary]; exact hi
    exact (hsub (e.symm i)).trans (hUint _ hmem)

-- pullbackbdry_zero: pullbackBdry sends the zero form to zero;
-- unfold to pullbackBdryFun, use ContMDiffSection.coe_zero + ContinuousLinearMap.map_zero
-- through the trivialization chain.
theorem pullbackbdry_zero {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M] :
    pullbackBdry (0 : DiffForm (𝓡∂ (n + 1)) M n) = 0 := by
  ext p
  simp only [pullbackBdry]
  change pullbackBdryFun 0 p = 0
  unfold pullbackBdryFun formInCoord
  simp only [ContMDiffSection.coe_zero, Pi.zero_apply, ContinuousLinearMap.map_zero]

-- pullbackbdry_add: pullbackBdry is additive in φ, via pointwise linearity of
-- formInCoord (Trivialization.continuousLinearMapAt is linear in the section value)
-- and the two CLMs compContinuousLinearMapCLM faceEmbedL and Trivialization.symmL.
theorem pullbackbdry_add {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (a b : DiffForm (𝓡∂ (n + 1)) M n) :
    pullbackBdry (a + b) = pullbackBdry a + pullbackBdry b := by
  ext p
  simp only [pullbackBdry, ContMDiffSection.coe_add, Pi.add_apply]
  change pullbackBdryFun (a + b) p = pullbackBdryFun a p + pullbackBdryFun b p
  simp only [pullbackBdryFun]
  have hfi : Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1)) (a + b) p.val
      (extChartAt (𝓡∂ (n + 1)) p.val p.val) =
      Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1)) a p.val
        (extChartAt (𝓡∂ (n + 1)) p.val p.val) +
      Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1)) b p.val
        (extChartAt (𝓡∂ (n + 1)) p.val p.val) := by
    simp only [Library.Geometry.Manifold.MExtDerivCoord.formInCoord, ContMDiffSection.coe_add,
      Pi.add_apply, map_add]
  rw [hfi]
  rw [(ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL).map_add]
  rw [(Trivialization.symmL ℝ (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
    (formBundleCore (𝓡 n) n).Fiber p) p).map_add]

-- pullbackBdry is additive (toFun/contMDiff bundled, both pointwise CLM reads), so package it
-- as `F : DiffForm (𝓡∂(n+1)) M n →+ DiffForm 𝓘(ℝ,…) (Bdry n M) n` and push the form-finsum
-- through it. Sub-goals: `pullbackbdry_add` (binary additivity) + `pullbackbdry_zero` (sends 0
-- to 0) supply `F`'s `map_add'`/`map_zero'`; `AddMonoidHom.map_finsum F hg` closes the goal.
theorem pullbackbdry_finsum_additive_generic {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type*} (g : ιM → DiffForm (𝓡∂ (n + 1)) M n)
    (hg : (Function.support g).Finite) :
    pullbackBdry (∑ᶠ i, g i) = ∑ᶠ i, pullbackBdry (g i)  := by
  let F : DiffForm (𝓡∂ (n + 1)) M n →+ DiffForm (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (Bdry n M) n :=
    { toFun := pullbackBdry
      map_zero' := pullbackbdry_zero
      map_add' := fun a b => pullbackbdry_add a b }
  exact AddMonoidHom.map_finsum F hg

theorem pullbackbdry_smul_finsum_eq {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type*} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    (∑ᶠ i, pullbackBdry (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ)) = pullbackBdry φ  := by
  have hg : (Function.support (fun i => smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff φ)).Finite := by
    haveI := B.fintype
    exact Set.toFinite _
  have hadd : pullbackBdry (∑ᶠ i, smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff φ)
      = ∑ᶠ i, pullbackBdry (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ) :=
    pullbackbdry_finsum_additive_generic _ hg
  have hself : (∑ᶠ i, smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff φ) = φ := smul_finsum_eq_self B φ
  rw [← hadd, hself]

theorem bump_pullbackbdry_family_finite {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type*} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) :
    (Function.support (fun i => pullbackBdry
      (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
        (B.toSmoothPartitionOfUnity i).contMDiff φ))).Finite  := by
  haveI := B.fintype
  exact Set.toFinite _

-- bdry_localcoeff_pullback_readout: pointwise readout of pullbackBdry via pullback_triv_read
-- + the topCoeff∘compCLM(faceEmbedL) kernel identity (face_embed_basis).
theorem bdry_localcoeff_pullback_readout {n : ℕ} {M : Type*} [TopologicalSpace M]
    [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M] [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (ψ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M)
    (y : EuclideanSpace ℝ (Fin n))
    (hy : y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target) :
    localCoeff (pullbackBdry ψ) p₀ y
      = Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1)) ψ p₀.val
          (extChartAt (𝓡∂ (n + 1)) p₀.val
            ((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y).val)
          (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)) := by
  simp only [localCoeff, topCoeff, Library.Geometry.Manifold.MExtDerivCoord.formInCoord]
  have hy_symm_mem : (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y ∈
      (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source := by
    have := (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).map_target hy
    rwa [extChartAt_source] at this
  rw [show (pullbackBdry ψ) ((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y) =
      pullbackBdryFun ψ ((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y) from rfl,
    Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ hy_symm_mem,
    pullback_triv_read ψ p₀ _ hy_symm_mem]
  simp only [ContinuousAlternatingMap.compContinuousLinearMapCLM_apply,
             ContinuousAlternatingMap.compContinuousLinearMap_apply]
  congr 1; funext i
  simp only [Function.comp_apply, Fin.removeNth, Fin.succAbove_zero]
  exact Library.Geometry.Manifold.FaceEmbedAlts.face_embed_basis i

-- Leaf-bypass: target-restricted ∂M coordinate brick. Pure `setIntegral_congr_fun`
-- over the shared ∂M chart target; pointwise the two integrands agree via the PROVED
-- `bdry_localcoeff_pullback_readout` (pullbackBdry coord readout) and
-- `extChartAt_val_eq_faceEmbed_chartAt` + `faceEmbed_eq_faceEmbedL` (center/point align,
-- using `hcenter : p₀.val = c₀`). No ℝⁿ extension, no support obligation, no s17500.

theorem bdry_chart_density_localcoeff_eq_face_pivot_on_target {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M) (hcenter : p₀.val = c₀) :
    ∫ y in (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
        localCoeff (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ)) p₀ y ∂MeasureTheory.volume
      = ∫ t in (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
          Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
            (smul_form (𝓡∂ (n + 1)) g hg φ) c₀ (faceEmbedL t)
            (Fin.removeNth 0 (EuclideanSpace.basisFun (Fin (n + 1)) ℝ)) ∂MeasureTheory.volume  := by
  apply MeasureTheory.setIntegral_congr_fun
  · exact (isOpen_extChartAt_target p₀).measurableSet
  · intro y hy
    rw [bdry_localcoeff_pullback_readout (smul_form (𝓡∂ (n + 1)) g hg φ) p₀ y hy]
    have hp : (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y ∈
        (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source := by
      have := (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).map_target hy
      rwa [extChartAt_source] at this
    have hpoint : extChartAt (𝓡∂ (n + 1)) p₀.val
        ((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y).val = faceEmbedL y := by
      rw [Library.Geometry.ManifoldBdry.FaceEmbedLemmas.extChartAt_val_eq_faceEmbed_chartAt p₀ _ hp,
        Library.Geometry.ManifoldBdry.FaceEmbedLemmas.faceEmbed_eq_faceEmbedL]
      congr 1
      have hr := (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).right_inv hy
      exact hr
    rw [hpoint, hcenter]

theorem per_chart_face_coord_stokes {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M) (hcenter : p₀.val = c₀) :
    (∫ y in (extChartAt (𝓡∂ (n + 1)) c₀).target,
        localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) c₀ y ∂MeasureTheory.volume)
      = - ∫ y in (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
          localCoeff (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ)) p₀ y ∂MeasureTheory.volume := by
  rw [mside_chart_density_localcoeff_eq_neg_face_pivot_on_target g hg c₀ hsupp φ p₀ hcenter, bdry_chart_density_localcoeff_eq_face_pivot_on_target g hg c₀ hsupp φ p₀ hcenter]

-- pullbackBdryFun ν p reads ν only at p.val through linear maps;
-- ν p.val = 0 implies pullbackBdry ν p = 0 via linearity chain.
theorem pullbackbdry_support_subset_val_preimage {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (ν : DiffForm (𝓡∂ (n + 1)) M n) :
    Function.support (fun p => (pullbackBdry ν) p)
      ⊆ (Subtype.val : Bdry n M → M) ⁻¹' Function.support (fun x => ν x) := by
  intro p hp
  simp only [Function.mem_support, Set.mem_preimage] at *
  intro hν
  apply hp
  change pullbackBdryFun ν p = 0
  -- formInCoord reads ν at p.val; ν p.val = 0 implies formInCoord = 0
  have hfic : formInCoord (𝓡∂ (n + 1)) ν p.val
      (extChartAt (𝓡∂ (n + 1)) p.val p.val) = 0 := by
    unfold formInCoord
    simp only []
    have hbase : (extChartAt (𝓡∂ (n + 1)) p.val).symm
        (extChartAt (𝓡∂ (n + 1)) p.val p.val) = p.val :=
      PartialEquiv.left_inv _ (mem_extChartAt_source p.val)
    rw [hbase, hν]
    exact (Trivialization.continuousLinearMapAt ℝ _ _).map_zero
  unfold pullbackBdryFun
  rw [hfic]
  exact (Trivialization.symmL ℝ _ p).map_zero

theorem pullbackbdry_tsupport_subset_val_preimage {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (ν : DiffForm (𝓡∂ (n + 1)) M n) :
    tsupport (fun p => (pullbackBdry ν) p)
      ⊆ Subtype.val ⁻¹' tsupport (fun x => ν x)  := by
  have hsupp := pullbackbdry_support_subset_val_preimage ν
  have hclosed : IsClosed
      ((Subtype.val : Bdry n M → M) ⁻¹' tsupport (fun x => ν x)) :=
    (isClosed_tsupport _).preimage continuous_subtype_val
  exact closure_minimal
    (hsupp.trans (Set.preimage_mono (subset_tsupport _))) hclosed

theorem pullbackbdry_smul_tsupport_subset {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M) (hcenter : p₀.val = c₀) :
    tsupport (fun x => (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ)) x)
      ⊆ (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source  := by
  calc tsupport (fun x => (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ)) x)
      ⊆ Subtype.val ⁻¹' tsupport (fun x => (smul_form (𝓡∂ (n + 1)) g hg φ) x) :=
          pullbackbdry_tsupport_subset_val_preimage (smul_form (𝓡∂ (n + 1)) g hg φ)
    _ ⊆ Subtype.val ⁻¹' tsupport (fun x => g x) :=
          Set.preimage_mono (tsupport_smul_subset_left (fun x => g x) (fun x => φ x))
    _ ⊆ Subtype.val ⁻¹' (chartAt (EuclideanHalfSpace (n + 1)) c₀).source :=
          Set.preimage_mono hsupp
    _ = (chartAt (EuclideanSpace ℝ (Fin n)) p₀).source := by
          subst hcenter
          change Subtype.val ⁻¹' (chartAt (EuclideanHalfSpace (n + 1)) p₀.val).source
             = Subtype.val ⁻¹' (extChartAt (𝓡∂ (n + 1)) p₀.val).source
          rw [extChartAt_source]

-- Factor `g` out of the boundary density.
-- Apply the proved readout `bdry_localcoeff_pullback_readout` to both pullbackBdry
-- terms, reducing to a coordinate identity; pull `g` through `formInCoord` of
-- `smul_form` via `formincoord_smul_form_factor` (generic trivialization linearity),
-- then `chart_symm_extchart_val_pin` (chart left-inverse) repins the `g`-argument.
theorem bdry_density_factors_through_g {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M] [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M)
    (y : EuclideanSpace ℝ (Fin n))
    (hy : y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target) :
    localCoeff (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ)) p₀ y
      = g (((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y).val) •
        localCoeff (pullbackBdry φ) p₀ y  := by
  rw [bdry_localcoeff_pullback_readout (smul_form (𝓡∂ (n + 1)) g hg φ) p₀ y hy,
      bdry_localcoeff_pullback_readout φ p₀ y hy,
      formincoord_smul_form_factor (𝓡∂ (n + 1)) g hg φ p₀.val _ _,
      chart_symm_extchart_val_pin p₀ y hy]

-- contrapositive: `g x = 0 ⇒ density = 0`, via the scalar factorization
-- `localCoeff(pullbackBdry(g•φ)) p₀ y = g x • localCoeff(pullbackBdry φ) p₀ y`
-- (readout + linearity of formInCoord through smul_form + chart left-inverse),
-- then `g x = 0` collapses the product to `0`.
theorem bdry_density_smul_nonzero_imp_g_nonzero {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [CompactSpace M] [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M)
    (y : EuclideanSpace ℝ (Fin n))
    (hy : y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target)
    (hne : localCoeff (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ)) p₀ y ≠ 0) :
    g (((extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).symm y).val) ≠ 0  := by
  contrapose! hne
  have hfact := bdry_density_factors_through_g g hg φ p₀ y hy
  rw [hfact, hne, zero_smul]

theorem bdensity_nonzero_face_in_gsupp_image {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M) (hcenter : p₀.val = c₀) :
    ∀ y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
      localCoeff (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ)) p₀ y ≠ 0 →
      faceEmbedL y ∈ ⇑(extChartAt (𝓡∂ (n + 1)) c₀) '' tsupport (fun x => g x)  := by
  intro y hy hne
  have h_g_ne := bdry_density_smul_nonzero_imp_g_nonzero g hg φ p₀ y hy hne
  have h_face_eq := face_embedl_eq_extchart_val c₀ p₀ hcenter y hy
  rw [h_face_eq]
  exact Set.mem_image_of_mem _ (subset_closure h_g_ne)

theorem bdry_pullback_interior_eq_zero {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (i : ιM)
    (hsupp : tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M) :
    pullbackBdry
        (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ) = 0  := by
  set ν : DiffForm (𝓡∂ (n + 1)) M n :=
    smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff φ
  have hdisj : ∀ p : Bdry n M, p.val ∉ Function.support (fun x => ν x) :=
    smul_form_support_misses_bdry B φ i hsupp
  ext p
  have hp : p ∉ Function.support (fun q => (pullbackBdry ν) q) := by
    intro h
    exact hdisj p (pullbackbdry_support_subset_val_preimage ν h)
  simpa using Function.notMem_support.mp hp

-- ∂M-side interior vanishing: the PoU-weighted form has support ⊆ tsupport (B i) ⊆ interior M,
-- which is disjoint from the boundary, so `pullbackBdry` of it is the zero form.
-- reduce to `bdry_pullback_interior_eq_zero` (form = 0), then `integral_zero` closes the goal.
theorem bdry_interior_integral_zero_hsupp {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (hB : B.IsSubordinate (fun x => (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (i : ιM)
    (hsupp : tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M) :
    DiffForm.integral (pullbackBdry
        (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ)) = 0  := by
  -- Support of the PoU-weighted form sits in tsupport (B i) ⊆ interior M, disjoint from ∂M,
  -- so its boundary pullback vanishes identically; integral of the zero form is 0.
  have h0 := bdry_pullback_interior_eq_zero B φ i hsupp
  rw [h0]
  exact Library.Geometry.Manifold.StokesIntegral.integral_zero

theorem formincoord_bdry_refform_eq_pos_smul_chartfun {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (p₀ : Bdry n M)
    (y : EuclideanSpace ℝ (Fin n))
    (hy : y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target) :
    ∃ c : ℝ, 0 < c ∧
      Library.Geometry.Manifold.MExtDerivCoord.formInCoord
          (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
          (OrientedManifold.refForm (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (N := Bdry n M)) p₀ y
        = c • Trivialization.continuousLinearMapAt ℝ
            (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
              (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p₀)
            ((extChartAt (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p₀).symm y)
            (Library.Geometry.Manifold.InducedOrientDefs.inducedOrientChartFun p₀
              ((extChartAt (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p₀).symm y))  := by
  have h_ray := inducedorientfun_eq_pos_smul_chartfun p₀ y hy
  obtain ⟨c, hc, heq⟩ := h_ray
  refine ⟨c, hc, ?_⟩
  have hform : Library.Geometry.Manifold.MExtDerivCoord.formInCoord
      (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
      (OrientedManifold.refForm (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (N := Bdry n M)) p₀ y
    = Trivialization.continuousLinearMapAt ℝ
        (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
          (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p₀)
        ((extChartAt (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p₀).symm y)
        (Library.Geometry.Manifold.InducedOrientDefs.inducedOrientFun
          ((extChartAt (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) p₀).symm y)) := rfl
  rw [hform, heq, map_smul]

-- Boundary refForm POSITIVE curried-face readout: localCoeff refForm_∂M p₀ y
--   = c·topCoeff(compface((formInCoord refForm_M c₀ (faceEmbedL y)).curryLeft (-e₀))), c>0.
-- localCoeff = topCoeff ∘ formInCoord (rfl); h_posray (pos-ray collapse: POU-glued
--   formInCoord readout = c • the p₀-chart trivialization readout of inducedOrientChartFun)
--   supplies c>0; h_readout (round-trip continuousLinearMapAt∘symmL + chart-compat via
--   hcenter) rewrites that readout to the target compface; topCoeff-of-smul flips c out.
theorem localcoeff_inducedorient_eq_pos_curried_face {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (c₀ : M) (p₀ : Bdry n M) (hcenter : p₀.val = c₀)
    (y : EuclideanSpace ℝ (Fin n))
    (hy : y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target) :
    ∃ c : ℝ, 0 < c ∧
      localCoeff
          (OrientedManifold.refForm (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (N := Bdry n M)) p₀ y
        = c * topCoeff (ContinuousAlternatingMap.compContinuousLinearMapCLM (faceEmbedL (n := n))
            ((Library.Geometry.Manifold.MExtDerivCoord.formInCoord (𝓡∂ (n + 1))
                (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) c₀
                (faceEmbedL y)).curryLeft
              (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)))  := by
  have h_readout := chartfun_clm_readout_eq_curried_face (n := n) (M := M) c₀ p₀ hcenter y hy
  have h_posray := formincoord_bdry_refform_eq_pos_smul_chartfun (n := n) (M := M) p₀ y hy
  obtain ⟨c, hc, hB⟩ := h_posray
  refine ⟨c, hc, ?_⟩
  have hloc : localCoeff
        (OrientedManifold.refForm (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (N := Bdry n M)) p₀ y
      = topCoeff (Library.Geometry.Manifold.MExtDerivCoord.formInCoord
          (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
          (OrientedManifold.refForm (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (N := Bdry n M))
          p₀ y) := rfl
  rw [hloc, hB, h_readout]
  simp only [topCoeff, ContinuousAlternatingMap.smul_apply, smul_eq_mul]

-- Boundary refForm value-level antimatch: localCoeff refForm_∂M p₀ y
--   = -(c * localCoeff refForm_M c₀ (faceEmbedL y)), c > 0.
-- h1: POSITIVE-scale curried-face readout. refForm_∂M = inducedOrient; pos-ray collapse
--   (inducedOrientChartFun_eq_pos_smul_self + POU) + trivialization readout
--   (trivializationAt_inducedOrientChartFun_eq) + chart-compat
--   (extChartAt_val_eq_faceEmbed_chartAt, faceEmbed_eq_faceEmbedL, hcenter) give
--   c * topCoeff(compface(α.curryLeft (-e₀))), α = formInCoord refForm_M c₀ (faceEmbedL y).
-- h2: generic alternating-oddness-in-slot-0 collapse
--   topCoeff(compface(β.curryLeft (-e₀))) = -topCoeff β (face_embed_basis + slot-0 linearity).
-- Combinator: obtain the positive scale from h1, rw h1+h2, simp [localCoeff]; ring flips the sign.
theorem localcoeff_inducedorient_eq_neg_pos_smul {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (c₀ : M) (p₀ : Bdry n M) (hcenter : p₀.val = c₀)
    (y : EuclideanSpace ℝ (Fin n))
    (hy : y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target) :
    ∃ c : ℝ, 0 < c ∧
      localCoeff
        (OrientedManifold.refForm (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (N := Bdry n M)) p₀ y
        = -(c * localCoeff
            (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) c₀ (faceEmbedL y)) := by
  have h1 := localcoeff_inducedorient_eq_pos_curried_face (M := M) c₀ p₀ hcenter y hy
  have h2 := @topcoeff_compface_curryneg_eq_neg_topcoeff n
  obtain ⟨c, hc, h1'⟩ := h1
  refine ⟨c, hc, ?_⟩
  rw [h1', h2]
  simp only [localCoeff]
  ring

theorem refform_sign_antimatch_at_bdry_center {n : ℕ} {M : Type*}
    [TopologicalSpace M] [T2Space M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M]
    [IsManifold (𝓡∂ (n + 1)) ∞ M] [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M) (hcenter : p₀.val = c₀)
    (y : EuclideanSpace ℝ (Fin n))
    (hy : y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target) :
    Real.sign (localCoeff
        (OrientedManifold.refForm (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (N := Bdry n M))
        p₀ y)
      = - Real.sign (localCoeff
          (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) c₀ (faceEmbedL y))  := by
  -- The boundary refForm reads the ambient refForm at the outward-normal frame `(-e₀, e₁,…,eₙ)`;
  -- top form is odd in slot 0, so the boundary coeff is a NEGATIVE positive-multiple of the
  -- ambient coeff (`localcoeff_inducedorient_eq_neg_pos_smul`); a `0 < c` sign-chase then flips
  -- `Real.sign` to give the minus (`real_sign_neg_pos_mul`).
  obtain ⟨c, hc, heq⟩ := localcoeff_inducedorient_eq_neg_pos_smul c₀ p₀ hcenter y hy
  rw [heq]
  exact real_sign_neg_pos_mul c _ hc

-- Leaf-bypass: S-superset variant of the proved s17640 (`sign_weighted_factor_antimatch`).
-- The internal preconnected support image is `Simg := extChartAt c₀ '' S` (S the superset),
-- preconnected via `hSconn.image` (extChartAt continuous on S ⊆ source) and ⊆ target by map_source.
-- The two density-localization legs land in `extChartAt c₀ '' tsupport g ⊆ Simg` (image-monotone
-- in `htsS`), so the PROVED mdensity/bdensity siblings still apply; one `epsM` from s17631 on the
-- whole preconnected `Simg`, both sides factored by `sign_const_factor_localcoeff`, ∂M side
-- antimatched to `-epsM` by `refform_sign_antimatch_at_bdry_center`.
theorem sign_weighted_factor_antimatch_gen {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M) (hcenter : p₀.val = c₀)
    (S : Set M) (hSconn : IsPreconnected S)
    (htsS : tsupport (fun x => g x) ⊆ S)
    (hSsource : S ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source) :
    ∃ epsM epsB : ℝ,
      (∫ y in (extChartAt (𝓡∂ (n + 1)) c₀).target,
          Real.sign (localCoeff (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M)) c₀ y)
            * localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) c₀ y
            ∂MeasureTheory.volume)
        = epsM • ∫ y in (extChartAt (𝓡∂ (n + 1)) c₀).target,
            localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) c₀ y
            ∂MeasureTheory.volume
      ∧ (∫ y in (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
          Real.sign (localCoeff
              (OrientedManifold.refForm (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (N := Bdry n M)) p₀ y)
            * localCoeff (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ)) p₀ y
            ∂MeasureTheory.volume)
        = epsB • ∫ y in (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
            localCoeff (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ)) p₀ y
            ∂MeasureTheory.volume
      ∧ epsB = - epsM  := by
  set Simg : Set (EuclideanSpace ℝ (Fin (n + 1))) :=
    ⇑(extChartAt (𝓡∂ (n + 1)) c₀) '' S with hSimg
  have hSsrc : S ⊆ (extChartAt (𝓡∂ (n + 1)) c₀).source := by
    rw [extChartAt_source]; exact hSsource
  have h1 : IsPreconnected Simg :=
    hSconn.image _ ((continuousOn_extChartAt c₀).mono hSsrc)
  have h2 : Simg ⊆ (extChartAt (𝓡∂ (n + 1)) c₀).target := by
    intro y hy
    obtain ⟨x, hx, rfl⟩ := hy
    exact (extChartAt (𝓡∂ (n + 1)) c₀).map_source (hSsrc hx)
  have hmono : ⇑(extChartAt (𝓡∂ (n + 1)) c₀) '' tsupport (fun x => g x) ⊆ Simg :=
    Set.image_mono htsS
  have h3 : ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) c₀).target,
      localCoeff (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) c₀ y ≠ 0 →
      y ∈ Simg :=
    fun y hy hne => hmono (mdensity_nonzero_in_gsupp_image g hg c₀ hsupp φ y hy hne)
  have h4 : ∀ y ∈ (extChartAt 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) p₀).target,
      localCoeff (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ)) p₀ y ≠ 0 →
      faceEmbedL y ∈ Simg :=
    fun y hy hne => hmono (bdensity_nonzero_face_in_gsupp_image g hg c₀ hsupp φ p₀ hcenter y hy hne)
  obtain ⟨epsM, hpm, hM⟩ :=
    sign_localcoeff_refform_const_on_preconnected (I := 𝓡∂ (n + 1)) (N := M) c₀ Simg h1 h2
  refine ⟨epsM, -epsM, ?_, ?_, rfl⟩
  · exact sign_const_factor_localcoeff _ c₀ epsM (fun y hy hne => hM y (h3 y hy hne))
  · refine sign_const_factor_localcoeff _ p₀ (-epsM) (fun y hy hne => ?_)
    rw [refform_sign_antimatch_at_bdry_center g hg c₀ hsupp φ p₀ hcenter y hy,
        hM (faceEmbedL y) (h4 y hy hne)]

theorem per_chart_stokes_at_bdry_center_gen {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (g : M → ℝ) (hg : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, ℝ) ∞ g) (c₀ : M)
    (hsupp : tsupport (fun x => g x) ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source)
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (p₀ : Bdry n M) (hcenter : p₀.val = c₀)
    (S : Set M) (hSconn : IsPreconnected S)
    (htsS : tsupport (fun x => g x) ⊆ S)
    (hSsource : S ⊆ (chartAt (EuclideanHalfSpace (n + 1)) c₀).source) :
    DiffForm.integral (mextDeriv (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) g hg φ))
      = DiffForm.integral (pullbackBdry
        (smul_form (𝓡∂ (n + 1)) g hg φ))  := by
  have hsuppL := mextderiv_smul_tsupport_subset g hg c₀ hsupp φ
  have hsuppR := pullbackbdry_smul_tsupport_subset g hg c₀ hsupp φ p₀ hcenter
  have hL := integral_single_chart_collapse (mextDeriv (𝓡∂ (n + 1)) (smul_form (𝓡∂ (n + 1)) g hg φ)) c₀ hsuppL
  have hR := integral_single_chart_collapse (pullbackBdry (smul_form (𝓡∂ (n + 1)) g hg φ)) p₀ hsuppR
  rw [← hL, ← hR]
  have hsigns := sign_weighted_factor_antimatch_gen g hg c₀ hsupp φ p₀ hcenter
    S hSconn htsS hSsource
  obtain ⟨epsM, epsB, hjm, hjb, hrel⟩ := hsigns
  have hunsigned := per_chart_face_coord_stokes g hg c₀ hsupp φ p₀ hcenter
  rw [hjm, hjb, hrel, hunsigned, smul_neg, neg_smul]

theorem bump_stokes_per_chart_centered {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    {ιM : Type} (B : SmoothBumpCovering ιM (𝓡∂ (n + 1)) M Set.univ)
    (hB : B.IsSubordinate (fun x => (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (φ : DiffForm (𝓡∂ (n + 1)) M n) (i : ιM)
    (hdich : B.c i ∉ (𝓡∂ (n + 1)).boundary M →
      tsupport (B i) ⊆ (𝓡∂ (n + 1)).interior M) :
    DiffForm.integral (mextDeriv (𝓡∂ (n + 1))
        (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ))
      = DiffForm.integral (pullbackBdry
        (smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
          (B.toSmoothPartitionOfUnity i).contMDiff φ))  := by
  by_cases hb : B.c i ∈ (𝓡∂ (n + 1)).boundary M
  · -- boundary case: generalized per-chart Stokes with preconnected superset S = tsupport (B i)
    have h_conn := bump_tsupport_preconnected B i
    have h_sub : tsupport (fun x => B.toSmoothPartitionOfUnity i x) ⊆ tsupport (B i) :=
      closure_mono (B.support_toSmoothPartitionOfUnity_subset i)
    exact per_chart_stokes_at_bdry_center_gen
      (B.toSmoothPartitionOfUnity i) (B.toSmoothPartitionOfUnity i).contMDiff (B.c i)
      (hB.toSmoothPartitionOfUnity i) φ ⟨B.c i, hb⟩ rfl
      (tsupport (B i)) h_conn h_sub (hB i)
  · -- interior case: support misses ∂M, both integrals vanish
    have hsupp := hdich hb
    have h_m := mside_interior_integral_zero_hsupp B hB φ i hsupp
    have h_b := bdry_interior_integral_zero_hsupp B hB φ i hsupp
    rw [h_m, h_b]

-- Boundary-centered clone of s11997: identical PoU-weighted calc, but the covering
-- comes from `exists_boundary_centered_bump_covering` (interior-centered bumps stay
-- interior, via hDich) so the per-chart leg can case-split center ∈ ∂M vs interior.
-- The per-i leg `bump_stokes_per_chart_centered_2` carries the per-i specialization
-- `hDich i` (matching the existing open goal seeded by s17648 so the cite links
-- rather than re-inserts); the four finsum/additivity legs are covering-generic
-- proved Library lemmas, cited unchanged.
theorem integral_mextDeriv_eq_integral_pullbackBdry : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M] [T2Space M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    [OrientedManifold (𝓡∂ (n + 1)) M] [CompactSpace M]
    [T2Space (Bdry n M)] [CompactSpace (Bdry n M)]
    (φ : DiffForm (𝓡∂ (n + 1)) M n),
    DiffForm.integral (mextDeriv (𝓡∂ (n + 1)) φ) = DiffForm.integral (pullbackBdry φ)  := by
  intro n M _ _ _ _ _ _ _ _ φ
  obtain ⟨ιM, B, hB, hDich⟩ := exists_boundary_centered_bump_covering (n := n) (M := M)
  set F : ιM → DiffForm (𝓡∂ (n + 1)) M n :=
    fun i => smul_form (𝓡∂ (n + 1)) (B.toSmoothPartitionOfUnity i)
      (B.toSmoothPartitionOfUnity i).contMDiff φ with hF
  calc DiffForm.integral (mextDeriv (𝓡∂ (n + 1)) φ)
      = DiffForm.integral (∑ᶠ i, mextDeriv (𝓡∂ (n + 1)) (F i)) :=
        congrArg DiffForm.integral (mextderiv_smul_finsum_eq B φ)
    _ = ∑ᶠ i, DiffForm.integral (mextDeriv (𝓡∂ (n + 1)) (F i)) :=
        diffform_integral_finsum_additive _ (bump_mextderiv_family_finite B φ)
    _ = ∑ᶠ i, DiffForm.integral (pullbackBdry (F i)) :=
        finsum_congr (fun i => bump_stokes_per_chart_centered B hB φ i (hDich i))
    _ = DiffForm.integral (∑ᶠ i, pullbackBdry (F i)) :=
        (diffform_integral_finsum_additive _ (bump_pullbackbdry_family_finite B φ)).symm
    _ = DiffForm.integral (pullbackBdry φ) :=
        congrArg DiffForm.integral (pullbackbdry_smul_finsum_eq B φ)

end Library.Geometry.Manifold.PerBumpStokes
