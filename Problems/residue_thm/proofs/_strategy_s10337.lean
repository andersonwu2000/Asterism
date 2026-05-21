import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_tau_partial_bound_ioo

namespace Problems.residue_thm

-- Reduce the a.e. bound on `uIoc 0 1` to the pointwise interior bound on `Ioo 0 1 × Ioo 0 1`.
-- The complement `uIoc 0 1 \ Ioo 0 1 = {1}` is null, so the strong sub-goal closes the a.e. one
-- after filter_upwards on `t ≠ 1`. Defers all analytic content (C² bounds on H, f, f') to the
-- interior-only sub-goal where `Icc 0 1 ∈ 𝓝 x` and `Icc 0 1 ∈ 𝓝 t` unlock the derivative formula.
theorem s10337
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∃ M : ℝ, ∀ᵐ t ∂MeasureTheory.volume,
      t ∈ Set.uIoc (0:ℝ) 1 → ∀ x ∈ Set.Ioo (0:ℝ) 1,
        ‖deriv (fun τ'' => f (H τ'' t) * deriv (H τ'') t) x‖ ≤ M  := by
  obtain ⟨M, hM⟩ :=
    tau_partial_bound_ioo hV hf hH hHV hH0 hH1
  refine ⟨M, ?_⟩
  have hae_ne : ∀ᵐ t ∂(MeasureTheory.volume : MeasureTheory.Measure ℝ), t ≠ (1:ℝ) :=
    MeasureTheory.measure_eq_zero_iff_ae_notMem.mp Real.volume_singleton
  filter_upwards [hae_ne] with t ht_ne ht_uioc x hx
  have ht_ioc : t ∈ Set.Ioc (0:ℝ) 1 := by
    rwa [← Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)]
  have ht_ioo : t ∈ Set.Ioo (0:ℝ) 1 := ⟨ht_ioc.1, lt_of_le_of_ne ht_ioc.2 ht_ne⟩
  exact hM t ht_ioo x hx

end Problems.residue_thm
