import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_dw_section_eq_deriv_at_ioo_point
import Problems.residue_thm.proofs.L_dw_section_t_eq_fderivwithin_dir_t

namespace Problems.residue_thm

-- Bridge `fderivWithin ... (τ',t) (0,1)` to `deriv (H τ') t` through the section
-- `derivWithin (H τ') (Icc 0 1) t`. Sub-goal A (lesson-34) ties `derivWithin` to
-- the joint `fderivWithin` in the t-direction; sub-goal B uses `t ∈ Ioo 0 1` so
-- `Icc 0 1 ∈ 𝓝 t` and `derivWithin = deriv` there.
theorem s10399
    {H : ℝ → ℝ → ℂ}
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (t : ℝ) (ht : t ∈ Set.Ioo (0:ℝ) 1) :
    ∀ τ' ∈ Set.Icc (0:ℝ) 1,
      fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ', t) (0, 1) =
        deriv (H τ') t  := by
  intro τ' hτ'
  have h_fderiv_eq_dw := dw_section_t_eq_fderivwithin_dir_t hH t ht τ' hτ'
  have h_dw_eq_deriv := dw_section_eq_deriv_at_ioo_point hH t ht τ' hτ'
  exact h_fderiv_eq_dw.symm.trans h_dw_eq_deriv

end Problems.residue_thm
