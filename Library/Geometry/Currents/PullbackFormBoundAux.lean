import Library.Geometry.Manifold.DiffFormBundle              -- DiffForm
import Library.Geometry.Manifold.StokesIntegralDefs           -- OrientedManifold, DiffForm.integral
import Mathlib.Algebra.Lie.OfAssociative
import Mathlib.Data.Real.StarOrdered
import Mathlib.Geometry.Manifold.PartitionOfUnity
import Library.Geometry.ManifoldBdry.PullbackFlatDNat         -- pullbackFlatForm

open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.PullbackFlatDNat
open Library.Geometry.ManifoldBdry.PullbackFlatForm
open scoped Manifold Bundle ContDiff
open scoped Manifold ContDiff

/-!
# Auxiliary bounds for pullback form integrals

This file collects analytic and geometric lemmas used to bound integrals of pullback forms
on compact manifolds with boundary, expressed via a smooth bump covering `B`.

## Main statements

- `finsum_abs_le`: triangle inequality for finite sums — $|\sum^{\mathsf{f}} g_i| \le
  (\sum^{\mathsf{f}} V_i) \cdot K$ given $|g_i| \le K \cdot V_i$.
- `fintype_uniform_bound`: promotes per-index bounds over a `Fintype` index to a single
  uniform bound.
- `prod_norm_le`: $\|a \cdot b \cdot c\| \le K$ for $a \in [0,1]$, $c \in \{-1,0,1\}$, $0 \le K$.
- `pou_nonzero_point_in_image`: a point where the partition of unity is nonzero lies in
  the chart image of the topological support.
- `chart_image_tsupport_compact`: the chart image of a POU bump's topological support is
  compact.
- `deriv_pow_norm_continuous_on`: the map $y \mapsto \|d(e \circ \phi^{-1})(y)\|^{n+1}$ is
  continuous on the chart image of the POU support.
- `chart_deriv_bound_on_image`: a single upper bound for the derivative norm power on the
  compact chart image.
- `per_chart_deriv_bound`: a per-chart derivative bound restricted to the POU-support region.
- `finite_cover_deriv_bound`: a uniform derivative bound over all charts in the finite covering.
-/

namespace Library.Geometry.Currents.PullbackFormBoundAux

set_option linter.unusedFintypeInType false in
/-- Triangle inequality for finite sums: $|\sum^{\mathsf{f}}_i g_i| \le$
$(\sum^{\mathsf{f}}_i V_i) \cdot K$ given $|g_i| \le K \cdot V_i$ for all $i$.

Proved by converting `∑ᶠ` to `Finset.sum` via `finsum_eq_sum_of_fintype`, then applying
`Finset.abs_sum_le_sum_abs` and `Finset.sum_le_sum`. -/
theorem finsum_abs_le {ι : Type*} [Fintype ι] (g V : ι → ℝ) (K : ℝ)
    (_hV : ∀ i, 0 ≤ V i) (h : ∀ i, |g i| ≤ K * V i) :
    |∑ᶠ i, g i| ≤ (∑ᶠ i, V i) * K := by
  simp_rw [finsum_eq_sum_of_fintype]
  calc |∑ i : ι, g i|
      ≤ ∑ i : ι, |g i| := Finset.abs_sum_le_sum_abs _ _
    _ ≤ ∑ i : ι, K * V i := Finset.sum_le_sum (fun i _ => h i)
    _ = (∑ i : ι, V i) * K := by rw [← Finset.mul_sum]; ring

set_option linter.unusedFintypeInType false in
/-- Given per-index upper bounds for $f(i, y)$ over sets $S_i$ with conditions $Q_i$,
produces a single uniform bound $D \ge 0$ valid for all $i$ in a `Fintype` index.

Proved by taking `Finset.univ.sup'` of the per-index bounds. -/
theorem fintype_uniform_bound {ι : Type*} [Fintype ι] {Y : Type*}
    (S : ι → Set Y) (Q : ι → Y → Prop) (f : ι → Y → ℝ)
    (h : ∀ i, ∃ D : ℝ, 0 ≤ D ∧ ∀ y ∈ S i, Q i y → f i y ≤ D) :
    ∃ D : ℝ, 0 ≤ D ∧ ∀ (i : ι), ∀ y ∈ S i, Q i y → f i y ≤ D := by
  by_cases hne : IsEmpty ι
  · exact ⟨0, le_refl 0, fun i => hne.elim i⟩
  · rw [not_isEmpty_iff] at hne
    haveI : Nonempty ι := hne
    let D_i : ι → ℝ := fun i => (h i).choose
    have hD_nonneg : ∀ i, 0 ≤ D_i i := fun i => ((h i).choose_spec).1
    have hD_bound : ∀ i y, y ∈ S i → Q i y → f i y ≤ D_i i :=
      fun i => ((h i).choose_spec).2
    refine ⟨Finset.univ.sup' Finset.univ_nonempty D_i, ?_, ?_⟩
    · exact le_trans (hD_nonneg (Classical.arbitrary ι))
        (Finset.le_sup' D_i (Finset.mem_univ _))
    · intro i y hy hQy
      exact le_trans (hD_bound i y hy hQy) (Finset.le_sup' D_i (Finset.mem_univ i))


/-- Norm bound $\|a \cdot b \cdot c\| \le K$ for $a \in [0, 1]$, $c \in \{-1, 0, 1\}$,
$|b| \le K$ when $a \ne 0$, and $K \ge 0$. -/
theorem prod_norm_le (a b c K : ℝ) (ha0 : 0 ≤ a) (ha1 : a ≤ 1)
    (hb : a ≠ 0 → |b| ≤ K) (hc : c = -1 ∨ c = 0 ∨ c = 1) (hK : 0 ≤ K) :
    ‖a * b * c‖ ≤ K := by
  rw [Real.norm_eq_abs, abs_mul, abs_mul, abs_of_nonneg ha0]
  rcases eq_or_ne a 0 with ha | ha
  · simp [ha, hK]
  · have hbK := hb ha
    rcases hc with rfl | rfl | rfl
    · simp only [abs_neg, abs_one, mul_one]; nlinarith [abs_nonneg b]
    · simp [hK]
    · simp only [abs_one, mul_one]; nlinarith [abs_nonneg b]

/-- If the partition-of-unity function `B.toSmoothPartitionOfUnity i` is nonzero at
`(extChartAt (𝓡∂ (n+1)) (B.c i)).symm y`, then `y` lies in the chart image of
`tsupport (B.toSmoothPartitionOfUnity i)`.

Proved by contrapositive: outside the topological support the function is zero
(`image_eq_zero_of_notMem_tsupport`), and the chart right-inverse recovers `y`. -/
theorem pou_nonzero_point_in_image
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [CompactSpace N]
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ)
    (i : ι) :
    ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
        B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y) ≠ 0 →
        y ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' (tsupport (B.toSmoothPartitionOfUnity i)) := by
  intro y hy hne
  refine ⟨(extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y, ?_, ?_⟩
  · by_contra h
    exact hne (image_eq_zero_of_notMem_tsupport h)
  · exact (extChartAt (𝓡∂ (n + 1)) (B.c i)).right_inv hy

/-- The chart image of the topological support of `B.toSmoothPartitionOfUnity i` is compact.

The support is contained in `tsupport (B i)` (via `closure_mono`), which is compact by
`hasCompactSupport`. The subordination hypothesis ensures the support lies inside the chart
source, so `IsCompact.image_of_continuousOn` with `continuousOn_extChartAt` applies. -/
theorem chart_image_tsupport_compact
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [CompactSpace N]
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ)
    (_hB : B.IsSubordinate (fun x ↦ (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (i : ι) :
    IsCompact
      ((extChartAt (𝓡∂ (n + 1)) (B.c i)) ''
        (tsupport (B.toSmoothPartitionOfUnity i))) := by
  have hsupp_sub : tsupport (B.toSmoothPartitionOfUnity i) ⊆ tsupport (B i) :=
    closure_mono (SmoothBumpCovering.support_toSmoothPartitionOfUnity_subset B i)
  have hcomp : IsCompact (tsupport (B i)) := (B i).hasCompactSupport.isCompact
  have hcomp_sub : IsCompact (tsupport (B.toSmoothPartitionOfUnity i)) :=
    hcomp.of_isClosed_subset (isClosed_tsupport _) hsupp_sub
  have hsource : tsupport (B.toSmoothPartitionOfUnity i) ⊆
      (extChartAt (𝓡∂ (n + 1)) (B.c i)).source :=
    hsupp_sub.trans (B i).tsupport_subset_extChartAt_source
  exact hcomp_sub.image_of_continuousOn ((continuousOn_extChartAt (B.c i)).mono hsource)

/-- The map $y \mapsto \|d(e \circ \phi_i^{-1})(y)\|^{n+1}$ is continuous on the chart image
of `tsupport (B.toSmoothPartitionOfUnity i)`, where $\phi_i$ is the extended chart at `B.c i`.

Follows from `pullback_flat_fderiv_within_chart_contdiffon` (smoothness of `e` in chart
coordinates) by composing `.continuousOn`, `.norm`, and `.pow`, then restricting via `.mono`
to the image (which lies in the chart target by subordination). -/
theorem deriv_pow_norm_continuous_on
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ)
    (_hB : B.IsSubordinate (fun x ↦ (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (i : ι) :
    ContinuousOn
      (fun y => ‖fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) (B.c i)).symm)
          (Set.range (𝓡∂ (n + 1))) y‖ ^ (n + 1))
      ((extChartAt (𝓡∂ (n + 1)) (B.c i)) '' (tsupport (B.toSmoothPartitionOfUnity i))) := by
  have h_cd := pullback_flat_fderiv_within_chart_contdiffon e he (B.c i)
  have h_cont := (h_cd.continuousOn.norm).pow (n + 1)
  have hsupp_sub : tsupport (B.toSmoothPartitionOfUnity i) ⊆ tsupport (B i) :=
    closure_mono (SmoothBumpCovering.support_toSmoothPartitionOfUnity_subset B i)
  have hsource : tsupport (B.toSmoothPartitionOfUnity i) ⊆
      (extChartAt (𝓡∂ (n + 1)) (B.c i)).source :=
    hsupp_sub.trans (B i).tsupport_subset_extChartAt_source
  have hS : (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' (tsupport (B.toSmoothPartitionOfUnity i))
      ⊆ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target := by
    calc (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' (tsupport (B.toSmoothPartitionOfUnity i))
        ⊆ (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' (extChartAt (𝓡∂ (n + 1)) (B.c i)).source :=
          Set.image_mono hsource
      _ = (extChartAt (𝓡∂ (n + 1)) (B.c i)).target :=
          (extChartAt (𝓡∂ (n + 1)) (B.c i)).image_source_eq_target
  exact h_cont.mono hS

/-- For each chart index `i`, there exists a bound $D \ge 0$ such that
$\|d(e \circ \phi_i^{-1})(y)\|^{n+1} \le D$ for all $y$ in the chart image of
`tsupport (B.toSmoothPartitionOfUnity i)`.

The chart image is compact (`chart_image_tsupport_compact`) and the derivative norm power
is continuous there (`deriv_pow_norm_continuous_on`), so `IsCompact.bddAbove_image` applies. -/
theorem chart_deriv_bound_on_image
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ)
    (hB : B.IsSubordinate (fun x ↦ (chartAt (EuclideanHalfSpace (n + 1)) x).source))
    (i : ι) :
    ∃ D : ℝ, 0 ≤ D ∧
      ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)) '' (tsupport (B.toSmoothPartitionOfUnity i)),
        ‖fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) (B.c i)).symm)
          (Set.range (𝓡∂ (n + 1))) y‖ ^ (n + 1) ≤ D := by
  have h_compact : IsCompact
      ((extChartAt (𝓡∂ (n + 1)) (B.c i)) '' (tsupport (B.toSmoothPartitionOfUnity i))) :=
    chart_image_tsupport_compact B hB i
  have h_cont : ContinuousOn
      (fun y => ‖fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) (B.c i)).symm)
          (Set.range (𝓡∂ (n + 1))) y‖ ^ (n + 1))
      ((extChartAt (𝓡∂ (n + 1)) (B.c i)) '' (tsupport (B.toSmoothPartitionOfUnity i))) :=
    deriv_pow_norm_continuous_on e he B hB i
  obtain ⟨b, hb⟩ := h_compact.bddAbove_image h_cont
  refine ⟨max 0 b, le_max_left 0 b, fun y hy => ?_⟩
  exact le_trans (hb ⟨y, hy, rfl⟩) (le_max_right 0 b)

/-- For each `i`, there exists a bound $D \ge 0$ such that
$\|d(e \circ \phi_i^{-1})(y)\|^{n+1} \le D$ for all `y` in the chart target where the
partition-of-unity `B.toSmoothPartitionOfUnity i` is nonzero at the preimage.

Combines `chart_deriv_bound_on_image` (bound on the compact chart image) with
`pou_nonzero_point_in_image` (nonzero POU implies membership in the image). -/
theorem per_chart_deriv_bound
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ)
    (hB : B.IsSubordinate (fun x ↦ (chartAt (EuclideanHalfSpace (n + 1)) x).source)) :
    ∀ (i : ι), ∃ D : ℝ, 0 ≤ D ∧
      ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
        B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y) ≠ 0 →
        ‖fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) (B.c i)).symm)
          (Set.range (𝓡∂ (n + 1))) y‖ ^ (n + 1) ≤ D := by
  intro i
  have h_bound := chart_deriv_bound_on_image e he B hB i
  have h_mem := pou_nonzero_point_in_image B i
  obtain ⟨D, hD0, hDb⟩ := h_bound
  exact ⟨D, hD0, fun y hy hpou => hDb y (h_mem y hy hpou)⟩

/-- A uniform upper bound $D \ge 0$ for the chart-coordinate derivative norm power
$\|d(e \circ \phi_i^{-1})(y)\|^{n+1}$, valid simultaneously for all chart indices `i`
in the finite `SmoothBumpCovering` and all relevant `y`.

Combines `per_chart_deriv_bound` (per-chart bound from compactness and smoothness of `e`)
with `fintype_uniform_bound` (finite maximum over the finitely-many charts, using
`B.fintype` from `CompactSpace N`). -/
theorem finite_cover_deriv_bound
    {n : ℕ} {N : Type*} [TopologicalSpace N] [T2Space N]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
    [CompactSpace N]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    (e : N → F) (he : ContMDiff (𝓡∂ (n + 1)) 𝓘(ℝ, F) ∞ e)
    {ι : Type*} (B : SmoothBumpCovering ι (𝓡∂ (n + 1)) N Set.univ)
    (hB : B.IsSubordinate (fun x ↦ (chartAt (EuclideanHalfSpace (n + 1)) x).source)) :
    ∃ D : ℝ, 0 ≤ D ∧ ∀ (i : ι),
      ∀ y ∈ (extChartAt (𝓡∂ (n + 1)) (B.c i)).target,
        B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y) ≠ 0 →
        ‖fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) (B.c i)).symm)
          (Set.range (𝓡∂ (n + 1))) y‖ ^ (n + 1) ≤ D := by
  haveI : Fintype ι := B.fintype
  exact fintype_uniform_bound
    (fun i => (extChartAt (𝓡∂ (n + 1)) (B.c i)).target)
    (fun i y => B.toSmoothPartitionOfUnity i ((extChartAt (𝓡∂ (n + 1)) (B.c i)).symm y) ≠ 0)
    (fun i y => ‖fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) (B.c i)).symm)
      (Set.range (𝓡∂ (n + 1))) y‖ ^ (n + 1))
    (per_chart_deriv_bound e he B hB)

end Library.Geometry.Currents.PullbackFormBoundAux
