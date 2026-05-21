import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- dw_integrand_continuous_on: continuity of derivWithin γ (Icc 0 1) / (γ - a) on Icc 0 1
-- Numerator: ContDiffOn.continuousOn_derivWithin; denominator: γ - a continuous and nonzero.
-- entry_kind: Builder
theorem dw_integrand_continuous_on
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ContinuousOn
      (fun t => derivWithin γ (Set.Icc (0:ℝ) 1) t / (γ t - a))
      (Set.Icc (0:ℝ) 1) := by
  apply ContinuousOn.div
  · exact hγ.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  · exact hγ.continuousOn.sub continuousOn_const
  · intro t ht
    exact sub_ne_zero.mpr (havoid t ht)

end Problems.residue_thm
