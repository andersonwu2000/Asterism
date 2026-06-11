import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle

namespace Problems.Geometry.stokes_mextderiv

-- ext_deriv_within_eq_of_mem_nhds_within: fderivWithin_of_mem_nhdsWithin closes the set-change goal
theorem ext_deriv_within_eq_of_mem_nhds_within {E F : Type*}
    [NormedAddCommGroup E] [NormedSpace ℝ E]
    [NormedAddCommGroup F] [NormedSpace ℝ F]
    {n : ℕ} {form : E → E [⋀^Fin n]→L[ℝ] F} {s t : Set E} {y : E}
    (hst : t ∈ nhdsWithin y s) (hs : UniqueDiffWithinAt ℝ s y)
    (hform : DifferentiableWithinAt ℝ form t y) :
    extDerivWithin form s y = extDerivWithin form t y := by
  simp only [extDerivWithin]
  congr 1
  exact fderivWithin_of_mem_nhdsWithin hst hs hform

end Problems.Geometry.stokes_mextderiv
