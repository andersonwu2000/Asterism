import Mathlib
import Library.Geometry.Manifold.DiffFormBundle
import Library.Geometry.Manifold.MExtDerivCoord
import Library.Geometry.Manifold.StokesIntegralDefs
import Problems.Geometry.integral_param.Defs
import Problems.Geometry.integral_param.proofs.L_top_coeff_comp_det

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.Manifold.MExtDerivCoord

namespace Problems.Geometry.integral_param

-- main: multi-chart density transition law — localCoeff transforms by the Jacobian determinant
-- of the chart transition map, proved by unfolding via topCoeff/formInCoord then citing
-- form_in_coord_pullback and top_coeff_comp_det.
theorem main : ∀ {d : ℕ} {EH : Type*} [TopologicalSpace EH]
    {I : ModelWithCorners ℝ (EuclideanSpace ℝ (Fin d)) EH}
    {N : Type*} [TopologicalSpace N] [ChartedSpace EH N] [IsManifold I ∞ N]
    (g : DiffForm I N d) (x x₀ : N) (y : EuclideanSpace ℝ (Fin d))
    (hy : y ∈ (extChartAt I x).target)
    (hy' : (extChartAt I x).symm y ∈ (chartAt EH x₀).source),
    localCoeff g x y
      = (fderivWithin ℝ (↑(extChartAt I x₀) ∘ ↑(extChartAt I x).symm) (Set.range I) y).det
        * localCoeff g x₀ (extChartAt I x₀ ((extChartAt I x).symm y)) := by
  intro d EH _ I N _ _ _ g x x₀ y hy hy'
  simp only [localCoeff]
  rw [form_in_coord_pullback I g x x₀ y hy hy']
  exact top_coeff_comp_det _ _

end Problems.Geometry.integral_param
