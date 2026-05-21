import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- differentiable_on_integral_of_continuous_on: FTC via integral_hasDerivWithinAt_right +
-- FTCFilter.nhdsIcc; ContinuousOn on Icc suffices for IntervalIntegrable and measurability.
theorem differentiable_on_integral_of_continuous_on
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (f : ℝ → ℂ)
    (hf : ContinuousOn f (Set.Icc (0 : ℝ) 1)) :
    DifferentiableOn ℝ (fun s => ∫ t in (0 : ℝ)..s, f t) (Set.Icc (0 : ℝ) 1) := by
  intro s hs
  haveI : Fact (s ∈ Set.Icc (0 : ℝ) 1) := ⟨hs⟩
  have hsub : Set.uIcc (0 : ℝ) s ⊆ Set.Icc 0 1 := by
    rw [Set.uIcc_of_le hs.1]; exact Set.Icc_subset_Icc_right hs.2
  apply (intervalIntegral.integral_hasDerivWithinAt_right
    ((hf.mono hsub).intervalIntegrable)
    ⟨Set.Icc 0 1, self_mem_nhdsWithin, hf.aestronglyMeasurable measurableSet_Icc⟩
    (hf s hs)).differentiableWithinAt

end Problems.residue_thm