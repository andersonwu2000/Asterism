import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem path_int_eq_winding_circle_int
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_repr : ∀ z : ℂ, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), P w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    {ε : ℝ} (hε_pos : 0 < ε)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t)
      = (Complex.windingNumber γ a : ℂ) * (∮ w in C(a, ε), P w) := by sorry

end Problems.residue_thm
