import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem p_cauchy_integral_repr
    {P : ℂ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0)) :
    ∀ z : ℂ, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a →
      P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(a, ε), P w / (w - z)) := by sorry

end Problems.residue_thm
