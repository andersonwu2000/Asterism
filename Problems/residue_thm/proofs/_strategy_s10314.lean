import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_dw_integrand_continuous_on

namespace Problems.residue_thm

-- FTC for `∫₀ˢ derivWithin γ (Icc 0 1) t / (γ t - a)` with derivative value
-- `derivWithin γ (Icc 0 1) s / (γ s - a)`. Sub-goal `dw_integrand_continuous_on`
-- (Builder): continuity of the integrand on `Icc 0 1` — drives both the integrability
-- and the pointwise FTC derivative-value via `integral_hasDerivWithinAt_right` under
-- the canonical `FTCFilter` instance on `nhdsWithin (Icc 0 1)`.
theorem s10314
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun s => ∫ t in (0:ℝ)..s, derivWithin γ (Set.Icc (0:ℝ) 1) t / (γ t - a))
        (derivWithin γ (Set.Icc (0:ℝ) 1) s / (γ s - a))
        (Set.Icc (0:ℝ) 1) s  := by
  have hcont := dw_integrand_continuous_on hγ hclosed havoid
  intro s hs
  have hsicc : s ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hs
  haveI : Fact (s ∈ Set.Icc (0:ℝ) 1) := ⟨hsicc⟩
  have hsub : Set.uIcc (0:ℝ) s ⊆ Set.Icc 0 1 := by
    rw [Set.uIcc_of_le hs.1]; exact Set.Icc_subset_Icc_right hsicc.2
  exact intervalIntegral.integral_hasDerivWithinAt_right
    ((hcont.mono hsub).intervalIntegrable)
    ⟨Set.Icc 0 1, self_mem_nhdsWithin, hcont.aestronglyMeasurable measurableSet_Icc⟩
    (hcont s hsicc)

end Problems.residue_thm
