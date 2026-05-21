import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_homotopy_integrand_hasderiv_in_tau
import Problems.residue_thm.proofs.L_homotopy_integrand_intervalintegrable
import Problems.residue_thm.proofs.L_homotopy_partial_tau_aemeasurable
import Problems.residue_thm.proofs.L_homotopy_partial_tau_uniform_bound

namespace Problems.residue_thm

-- Apply Mathlib's parametric interval-integral Leibniz at τ ∈ Ioo 0 1
-- (where Ioo 0 1 ∈ 𝓝 τ unlocks the lemma). Sub-goals provide: integrand
-- IntervalIntegrable on [0,1] (1), τ-partial AEStronglyMeasurable (2), uniform
-- L∞ bound on the τ-partial over Ioo 0 1 (3), and pointwise HasDerivAt of the
-- integrand in τ for a.e. t over Ioo 0 1 (4). Combinator:
-- intervalIntegral.hasDerivAt_integral_of_dominated_loc_of_deriv_le with
-- s := Ioo 0 1 and bound := const M.
theorem s10334
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt (fun τ' => ∫ t in (0:ℝ)..1, f (H τ' t) * deriv (H τ') t)
        (∫ t in (0:ℝ)..1, deriv (fun τ' => f (H τ' t) * deriv (H τ') t) τ) τ  := by
  intro τ hτ
  have hs_mem : Set.Ioo (0:ℝ) 1 ∈ nhds τ := isOpen_Ioo.mem_nhds hτ
  have h_int := homotopy_integrand_intervalintegrable hV hf hH hHV hH0 hH1
  have h_partial_meas := homotopy_partial_tau_aemeasurable hV hf hH hHV hH0 hH1
  obtain ⟨M, h_bound⟩ := homotopy_partial_tau_uniform_bound hV hf hH hHV hH0 hH1
  have h_pointwise := homotopy_integrand_hasderiv_in_tau hV hf hH hHV hH0 hH1
  have h_meas_near : ∀ᶠ x in nhds τ,
      MeasureTheory.AEStronglyMeasurable
        (fun t => f (H x t) * deriv (H x) t)
        (MeasureTheory.volume.restrict (Set.uIoc (0:ℝ) 1)) := by
    filter_upwards [hs_mem] with x hx
    have h := (h_int x (Set.Ioo_subset_Icc_self hx)).aestronglyMeasurable
    rwa [Set.uIoc_of_le (zero_le_one (α := ℝ))]
  exact (intervalIntegral.hasDerivAt_integral_of_dominated_loc_of_deriv_le
    (𝕜 := ℝ) (a := (0:ℝ)) (b := 1) (μ := MeasureTheory.volume)
    (s := Set.Ioo (0:ℝ) 1) (bound := fun _ => M)
    hs_mem h_meas_near (h_int τ (Set.Ioo_subset_Icc_self hτ))
    (h_partial_meas τ hτ) h_bound intervalIntegrable_const h_pointwise).2

end Problems.residue_thm
