import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs.L_form_in_coord_pullback

namespace Problems.Geometry.stokes_mextderiv

open scoped Manifold Bundle ContDiff Topology
open Bundle
open Library.Geometry.Manifold.DiffFormBundle


-- Locality: the proved sibling form_in_coord_pullback (roles of x, x₀ swapped) gives the
-- pointwise identity formInCoord I φ x₀ y = pullback form, valid on the set
-- (extChartAt I x₀).target ∩ (extChartAt I x₀).symm ⁻¹' (chartAt H x).source, which is a
-- 𝓝[range I]-neighborhood of extChartAt I x₀ x; Filter.EventuallyEq.extDerivWithin_eq
-- transports the equality through extDerivWithin.
theorem s11694
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {H : Type*} [TopologicalSpace H]
    (I : ModelWithCorners ℝ E H)
    {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]
    {k : ℕ} (φ : DiffForm I M k) (x₀ x : M)
    (hx : x ∈ (chartAt H x₀).source) :
    extDerivWithin (formInCoord I φ x₀) (Set.range I) (extChartAt I x₀ x)
      = extDerivWithin
          (fun y => (formInCoord I φ x
              ((↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) y)).compContinuousLinearMap
            (fderivWithin ℝ (↑(extChartAt I x) ∘ ↑(extChartAt I x₀).symm) (Set.range I) y))
          (Set.range I) (extChartAt I x₀ x)  := by
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

end Problems.Geometry.stokes_mextderiv
