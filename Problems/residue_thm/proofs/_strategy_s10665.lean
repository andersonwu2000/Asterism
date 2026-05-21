import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c1_const_add_indefinite_integral
import Problems.residue_thm.proofs.L_piecewise_velocity_continuous_on_icc

namespace Problems.residue_thm

-- Decompose `ContDiffOn ℝ 1` of the integral primitive into:
-- (1) continuity of the piecewise velocity on `Icc 0 1` (flat-endpoint joins at 1/2),
-- (2) the generic FTC fact that a constant plus the indefinite integral of a continuous
--     function on `Icc 0 1` is `ContDiffOn ℝ 1` on `Icc 0 1`.
theorem s10665
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContDiffOn ℝ 1
        (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        (Set.Icc 0 1)  := by
  have h_cont := piecewise_velocity_continuous_on_icc hα' hβ' hα'_deriv hβ'_deriv
  exact c1_const_add_indefinite_integral (α' 0) _ h_cont

end Problems.residue_thm
