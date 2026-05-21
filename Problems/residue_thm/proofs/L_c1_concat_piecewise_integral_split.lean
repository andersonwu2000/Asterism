import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

theorem c1_concat_piecewise_integral_split
    {Q : ℂ → ℂ} {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    (∫ t in (0 : ℝ)..1,
        Q ((fun t : ℝ => if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1)) t) *
          deriv (fun t : ℝ => if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1)) t) =
      (∫ t in (0 : ℝ)..1, Q (α' t) * deriv α' t) +
      (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t) := by hint

end Problems.residue_thm
