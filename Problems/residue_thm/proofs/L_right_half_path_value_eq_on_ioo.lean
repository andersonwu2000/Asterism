import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_flat_concat_ftc_right_half

namespace Problems.residue_thm

-- right_half_path_value_eq_on_ioo: restrict the Icc result to Ioo via flat_concat_ftc_right_half
theorem right_half_path_value_eq_on_ioo
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Ioo (1/2 : ℝ) 1,
      (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t
        = β' (2*t - 1) := by
  intro t ht
  exact flat_concat_ftc_right_half hα' hβ' h_match hα'_deriv hβ'_deriv t
    ⟨ht.1.le, ht.2.le⟩

end Problems.residue_thm
