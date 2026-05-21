import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_fderiv_within_dir_t_eq_deriv_t_section

namespace Problems.residue_thm

-- Two τ'-functions agree pointwise on `Icc 0 1`:
--   F τ' = fderivWithin H U (τ', t) (0,1)   and   G τ' = deriv (H τ') t.
-- The pointwise identity uses lesson-34 in the t-direction (uses `t ∈ Ioo 0 1`
-- so `Icc 0 1 ∈ 𝓝 t`, unlocking `fderivWithin (·,t)→(0,1) = deriv (H τ') t`).
-- Apply `derivWithin_congr` to lift pointwise equality to derivWithin equality at τ.
theorem s10393
    {H : ℝ → ℝ → ℂ}
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1)) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      derivWithin (fun τ' =>
            (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
                (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t)) (0, 1))
          (Set.Icc (0:ℝ) 1) τ =
        derivWithin (fun τ' => deriv (H τ') t) (Set.Icc (0:ℝ) 1) τ  := by
  intro τ hτ t ht
  have h_sub := fderiv_within_dir_t_eq_deriv_t_section hH t ht
  refine derivWithin_congr (fun τ' hτ' => h_sub τ' hτ') ?_
  exact h_sub τ (Set.Ico_subset_Icc_self hτ)


end Problems.residue_thm
