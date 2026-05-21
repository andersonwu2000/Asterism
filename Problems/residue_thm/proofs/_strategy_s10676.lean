import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_left_half_eval_wrap
import Problems.residue_thm.proofs.L_right_half_eval_wrap
import Problems.residue_thm.proofs.L_split_at_half_wrap

namespace Problems.residue_thm

-- Split ∫₀..t = ∫₀..(1/2) + ∫(1/2)..t at the midpoint; evaluate each half via FTC;
-- the left half collapses to α'(1) - α'(0), the right half to β'(2t-1) - β'(0);
-- the constant α'(0) + (α'(1) - α'(0)) cancels via h_match : α'(1) = β'(0).
theorem s10676
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc ((1:ℝ)/2) 1,
      (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
        (if s ≤ (1:ℝ)/2
          then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t = β' (2*t - 1)  := by
  intro t ht
  have h_split := split_at_half_wrap hα' hβ' h_match hα'_deriv hβ'_deriv t ht
  have h_left := left_half_eval_wrap hα' hβ' h_match hα'_deriv hβ'_deriv
  have h_right := right_half_eval_wrap hα' hβ' h_match hα'_deriv hβ'_deriv t ht
  dsimp only
  rw [h_split, h_left, h_right, h_match]
  ring

end Problems.residue_thm
