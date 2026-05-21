import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- integral_eq_integral_deriv_within: ae-equality of deriv/derivWithin integrands on Icc 0 1
-- Uses derivWithin_of_mem_nhds: for t in Ioo 0 s, Icc 0 1 is a nhd, so derivWithin = deriv.
-- Singleton {s} has measure 0, handled via MeasureTheory.ae_iff + Real.volume_singleton.
theorem integral_eq_integral_deriv_within
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Icc (0:ℝ) 1,
      (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) =
        (∫ t in (0:ℝ)..s, derivWithin γ (Set.Icc (0:ℝ) 1) t / (γ t - a)) := by
  intro s hs
  have hs0 : (0:ℝ) ≤ s := hs.1
  have hs1 : s ≤ 1 := hs.2
  apply intervalIntegral.integral_congr_ae
  have hne : ∀ᵐ (x : ℝ), x ≠ s := by
    rw [MeasureTheory.ae_iff]; simp
  filter_upwards [hne] with t hts ht
  simp only [Set.uIoc_of_le hs0, Set.mem_Ioc] at ht
  congr 1
  symm
  apply derivWithin_of_mem_nhds
  exact Icc_mem_nhds ht.1 (lt_of_lt_of_le (lt_of_le_of_ne ht.2 hts) hs1)
end Problems.residue_thm
