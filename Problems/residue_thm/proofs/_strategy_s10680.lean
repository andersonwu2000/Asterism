import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_piecewise_f_eveq_right_split_on_ioo
import Problems.residue_thm.proofs.L_right_split_has_deriv_at_on_ioo

namespace Problems.residue_thm

-- For t ∈ Ioo (1/2) 1, the piecewise integral function F(t) is eventually equal
-- (on a neighborhood of t) to the split form G(t) = α'(0) + ∫₀^(1/2) (left branch) +
-- ∫_(1/2)^t (right branch), whose derivative at t is 2·derivWithin β' (Icc 0 1) (2t-1)
-- by FTC. Combine via HasDerivAt.congr_of_eventuallyEq and .deriv.
theorem s10680
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Ioo (1/2 : ℝ) 1,
      deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t
        = 2 * derivWithin β' (Set.Icc 0 1) (2*t - 1)  := by
  have h_evEq := piecewise_f_eveq_right_split_on_ioo (α' := α') (β' := β') hα' hβ'
  have h_deriv := right_split_has_deriv_at_on_ioo (α' := α') (β' := β') hβ'
  intro t ht
  exact ((h_deriv t ht).congr_of_eventuallyEq (h_evEq t ht)).deriv

end Problems.residue_thm
