import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- integral_eq_integral_deriv_within_2: integrands deriv γ and derivWithin γ (Icc 0 1) agree
-- a.e. on [0,s], so the interval integrals coincide; the only disagreement is at {0,s}
-- (measure zero), where derivWithin differs from deriv; at interior points Icc 0 1 ∈ nhds t.
theorem integral_eq_integral_deriv_within_2
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Icc (0:ℝ) 1,
      (∫ t in (0:ℝ)..s, deriv γ t / (γ t - a)) =
        (∫ t in (0:ℝ)..s, derivWithin γ (Set.Icc (0:ℝ) 1) t / (γ t - a)) := by
  intro s hs
  apply intervalIntegral.integral_congr_ae'
  · have hne : ∀ᵐ x ∂(MeasureTheory.volume : MeasureTheory.Measure ℝ), x ≠ s := by
      rw [MeasureTheory.ae_iff]
      simp only [ne_eq, not_not]
      exact Real.volume_singleton
    filter_upwards [hne] with x hxs hxIoc
    have hx : x ∈ Set.Ioo 0 s := ⟨hxIoc.1, lt_of_le_of_ne hxIoc.2 hxs⟩
    have hx1 : x ∈ Set.Ioo (0:ℝ) 1 := ⟨hx.1, lt_of_lt_of_le hx.2 hs.2⟩
    rw [derivWithin_of_mem_nhds (Icc_mem_nhds hx1.1 hx1.2)]
  · exact Filter.Eventually.of_forall fun x hxIoc =>
      absurd hxIoc.2 (not_le.mpr (lt_of_le_of_lt hs.1 hxIoc.1))

end Problems.residue_thm
