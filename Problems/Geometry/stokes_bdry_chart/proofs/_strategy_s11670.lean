import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs

namespace Problems.Geometry.stokes_bdry_chart

open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

-- Direct coordinate proof: `ext j`, split `j` via `Fin.cases` into the normal
-- coordinate `0` (where `h0` and `Fin.succ_ne_zero` kill every summand) and a
-- face coordinate `i.succ` (where `Pi.single_apply` + `Fin.succ_inj` collapse
-- the `faceEmbed` sum to the single matching term `w i.succ`).
theorem s11670 {n : ℕ} (w : EuclideanSpace ℝ (Fin (n + 1)))
    (h0 : w 0 = 0) : faceEmbed (faceProj w) = w  := by
  ext j
  simp only [Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.faceEmbed, faceProj,
    EuclideanSpace.basisFun_apply]
  refine Fin.cases ?_ ?_ j
  · simp [(Fin.succ_ne_zero _).symm, h0]
  · intro i
    simp [Pi.single_apply, Fin.succ_inj]

end Problems.Geometry.stokes_bdry_chart
