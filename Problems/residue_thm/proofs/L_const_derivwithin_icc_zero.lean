import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- const_derivwithin_icc_zero: constant-on-Icc function has derivWithin = 0;
-- applies HasDerivWithinAt.congr from hasDerivWithinAt_const + uniqueDiffOn_Icc_zero_one
theorem const_derivwithin_icc_zero
    {g : ℝ → ℂ} (hg : ∀ τ ∈ Set.Icc (0 : ℝ) 1, g τ = g 0) :
    ∀ τ ∈ Set.Ico (0 : ℝ) 1, derivWithin g (Set.Icc (0 : ℝ) 1) τ = 0 := by
  intro τ hτ
  have hmem : τ ∈ Set.Icc (0 : ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have hconst : HasDerivWithinAt (fun _ => g 0) 0 (Set.Icc (0 : ℝ) 1) τ :=
    hasDerivWithinAt_const τ (Set.Icc (0 : ℝ) 1) (g 0)
  have h0 : HasDerivWithinAt g 0 (Set.Icc (0 : ℝ) 1) τ :=
    hconst.congr (fun y hy => hg y hy) (hg τ hmem)
  exact h0.derivWithin (uniqueDiffOn_Icc_zero_one τ hmem)

end Problems.residue_thm
