import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct leaf proof of the z-axis rotation composition law M(θ)·M(φ) = M(θ+φ).
-- Rewrite cos/sin of the sum via the angle-addition formulas, then check the 9
-- matrix entries: `ext` + `fin_cases` reduces to scalar `Fin.sum_univ_three`
-- products closed by `ring`. No sub-goals needed.
theorem s11436 (θ φ : ℝ) :
    (!![Real.cos θ, -Real.sin θ, 0;
        Real.sin θ,  Real.cos θ, 0;
        0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) *
      !![Real.cos φ, -Real.sin φ, 0;
         Real.sin φ,  Real.cos φ, 0;
         0,           0,          1]
      = !![Real.cos (θ + φ), -Real.sin (θ + φ), 0;
           Real.sin (θ + φ),  Real.cos (θ + φ), 0;
           0,                 0,                1]  := by
  rw [Real.cos_add, Real.sin_add]
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.mul_apply, Fin.sum_univ_three] <;> ring

end Problems.Geometry.banach_tarski
