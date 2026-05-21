import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- subst_alpha_chain_rule_left: integrand equality via h = α'(2t) and chain rule deriv h t = 2·deriv α'(2t)
theorem subst_alpha_chain_rule_left
    {Q : ℂ → ℂ} {α' h : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_left : ∀ t ∈ Set.Icc (0 : ℝ) (1 / 2), h t = α' (2 * t)) :
    (∫ t in (0 : ℝ)..(1 / 2 : ℝ), Q (h t) * deriv h t) =
      (∫ t in (0 : ℝ)..(1 / 2 : ℝ), 2 * (Q (α' (2 * t)) * deriv α' (2 * t))) := by
  apply intervalIntegral.integral_congr_ae
  have hne : ∀ᵐ t ∂MeasureTheory.volume, t ≠ (1 / 2 : ℝ) := by
    rw [MeasureTheory.ae_iff]
    simp [MeasureTheory.measure_singleton]
  filter_upwards [hne] with t hne_t ht_uIoc
  rw [Set.uIoc_of_le (by norm_num : (0 : ℝ) ≤ 1 / 2)] at ht_uIoc
  have htIoo : t ∈ Set.Ioo (0 : ℝ) (1 / 2) :=
    ⟨ht_uIoc.1, lt_of_le_of_ne ht_uIoc.2 hne_t⟩
  have hht : h t = α' (2 * t) := hh_left t (Set.Ioo_subset_Icc_self htIoo)
  have hderiv_h_eq : deriv h t = deriv (fun s => α' (2 * s)) t := by
    apply Filter.EventuallyEq.deriv_eq
    apply Filter.eventually_of_mem (Ioo_mem_nhds htIoo.1 htIoo.2)
    intro s hs
    exact hh_left s ⟨le_of_lt hs.1, le_of_lt hs.2⟩
  have h2t_mem : 2 * t ∈ Set.Ioo (0 : ℝ) 1 :=
    ⟨by linarith [htIoo.1], by linarith [htIoo.2]⟩
  have hIcc_nhds : Set.Icc (0 : ℝ) 1 ∈ nhds (2 * t) :=
    Filter.mem_of_superset (Ioo_mem_nhds h2t_mem.1 h2t_mem.2) Set.Ioo_subset_Icc_self
  have hdα_at : DifferentiableAt ℝ α' (2 * t) :=
    (hα'.differentiableOn (by norm_num)).differentiableAt hIcc_nhds
  have hd2 : HasDerivAt (fun s : ℝ => 2 * s) (2 : ℝ) t := by
    have := (hasDerivAt_id t).const_mul (2 : ℝ); simpa using this
  have hchain : deriv (fun s => α' (2 * s)) t = (2 : ℝ) • deriv α' (2 * t) :=
    (hdα_at.hasDerivAt.scomp t hd2).deriv
  rw [hht, hderiv_h_eq, hchain,
      show (2 : ℝ) • deriv α' (2 * t) = (2 : ℂ) * deriv α' (2 * t) from by
        rw [Algebra.smul_def]; norm_cast]
  ring

end Problems.residue_thm
