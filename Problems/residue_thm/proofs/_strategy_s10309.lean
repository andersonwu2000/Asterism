import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integrand_continuous_on

namespace Problems.residue_thm

-- FTC + extracted continuity hypothesis: derivative of `∫₀ˢ deriv γ t / (γ t - a)` is the integrand at `s`.
-- Sub `integrand_continuous_on` packages continuity of the integrand on `Icc 0 1` (uses `havoid` for non-vanishing denominator);
-- `integral_hasDerivWithinAt_right` then yields the FTC HasDerivWithinAt at every `s ∈ Ico 0 1` using the `Fact (s ∈ Icc 0 1)`-backed `FTCFilter` instance.
theorem s10309
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt (fun s => ∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))
        (deriv γ s / (γ s - a)) (Set.Icc (0:ℝ) 1) s  := by
  intro s hs
  have h_cont := integrand_continuous_on hγ hclosed havoid
  have hs_icc : s ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hs
  haveI : Fact (s ∈ Set.Icc (0:ℝ) 1) := ⟨hs_icc⟩
  apply intervalIntegral.integral_hasDerivWithinAt_right
  · refine ContinuousOn.intervalIntegrable_of_Icc hs.1 ?_
    exact h_cont.mono (Set.Icc_subset_Icc_right hs.2.le)
  · exact h_cont.stronglyMeasurableAtFilter_nhdsWithin measurableSet_Icc s
  · exact h_cont.continuousWithinAt hs_icc

end Problems.residue_thm
