import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_concat_flat_paths_integral_split
import Problems.residue_thm.proofs.L_reparam_flat_endpoints_wrap

namespace Problems.residue_thm

-- Reduce to flat-ended concat: smooth-reparam α and β so their endpoint
-- derivWithin vanishes (preserving endpoints + integrals), then glue the
-- flat-ended pair via the standard piecewise concat with integral split.
theorem s10659
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α β : ℝ → ℂ}
    (hα : ContDiffOn ℝ 1 α (Set.Icc 0 1))
    (hα_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α t ≠ a)
    (hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1))
    (hβ_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β t ≠ a)
    (h_match : α 1 = β 0) :
    ∃ αβ : ℝ → ℂ,
      ContDiffOn ℝ 1 αβ (Set.Icc 0 1) ∧
      αβ 0 = α 0 ∧
      αβ 1 = β 1 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, αβ t ≠ a) ∧
      (∫ t in (0 : ℝ)..1, Q (αβ t) * deriv αβ t) =
        (∫ t in (0 : ℝ)..1, Q (α t) * deriv α t) +
        (∫ t in (0 : ℝ)..1, Q (β t) * deriv β t) := by
  have h_reparam_alpha := reparam_flat_endpoints_wrap (Q := Q) hα hα_avoid
  have h_reparam_beta := reparam_flat_endpoints_wrap (Q := Q) hβ hβ_avoid
  obtain ⟨α', hα'_cdf, hα'0, hα'1, _hα'_d0, hα'_d1, hα'_av, hα'_int⟩ :=
    h_reparam_alpha
  obtain ⟨β', hβ'_cdf, hβ'0, hβ'1, hβ'_d0, _hβ'_d1, hβ'_av, hβ'_int⟩ :=
    h_reparam_beta
  have h_match' : α' 1 = β' 0 := by rw [hα'1, hβ'0]; exact h_match
  have h_concat :=
    concat_flat_paths_integral_split (Q := Q) hQ_an
      hα'_cdf hα'_av hβ'_cdf hβ'_av h_match' hα'_d1 hβ'_d0
  obtain ⟨αβ, hαβ_cdf, hαβ0, hαβ1, hαβ_av, hαβ_int⟩ := h_concat
  refine ⟨αβ, hαβ_cdf, ?_, ?_, hαβ_av, ?_⟩
  · rw [hαβ0, hα'0]
  · rw [hαβ1, hβ'1]
  · rw [hαβ_int, hα'_int, hβ'_int]

end Problems.residue_thm
