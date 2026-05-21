import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- continuous_on_integrand: ContinuousOn of (derivWithin γ / (γ - a)) on Icc 0 1 via
-- ContDiffOn.continuousOn_derivWithin + ContinuousOn.div with havoid non-vanishing
theorem continuous_on_integrand
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ContinuousOn
      (fun t => derivWithin γ (Set.Icc (0 : ℝ) 1) t / (γ t - a))
      (Set.Icc (0 : ℝ) 1) := by
  have h1 : ContinuousOn (derivWithin γ (Set.Icc (0 : ℝ) 1)) (Set.Icc (0 : ℝ) 1) :=
    hγ.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have h2 : ContinuousOn (fun t => γ t - a) (Set.Icc (0 : ℝ) 1) :=
    hγ.continuousOn.sub continuousOn_const
  have h3 : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t - a ≠ 0 :=
    fun t ht => sub_ne_zero.mpr (havoid t ht)
  exact h1.div h2 h3

end Problems.residue_thm

