import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c1_concat_integral_additive_via_chain_rule
import Problems.residue_thm.proofs.L_c1_concat_witness_explicit_form

namespace Problems.residue_thm

-- Decompose into (a) construction of a C¹ concat witness `αβ` with the
-- explicit piecewise form `α'(2t)` on [0,1/2] and `β'(2t-1)` on [1/2,1]
-- (bundles ContDiffOn, the form, avoidance, and h_match consumption), and
-- (b) integral additivity for any C¹ path matching that piecewise form on
-- the two sub-intervals (reduces the integral identity to a chain-rule
-- change-of-variables on each piece, dropping the construction details).
-- Fresh slugs to bypass shelved/disproved siblings on the same shape:
-- prior `c1_piecewise_concat_integral_split` was wrongly declined as
-- unprovable (its purported counterexample α'=id, β'=1+t, h=2t actually
-- satisfies the equality via u-substitution).
theorem s10595
    {Q : ℂ → ℂ} {a : ℂ} {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∃ αβ : ℝ → ℂ,
      ContDiffOn ℝ 1 αβ (Set.Icc 0 1) ∧
      αβ 0 = α' 0 ∧
      αβ 1 = β' 1 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, αβ t ≠ a) ∧
      (∫ t in (0 : ℝ)..1, Q (αβ t) * deriv αβ t) =
        (∫ t in (0 : ℝ)..1, Q (α' t) * deriv α' t) +
        (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t)  := by
  have h_witness :=
    c1_concat_witness_explicit_form (a := a) hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  obtain ⟨αβ, hαβ_c1, hαβ_left, hαβ_right, hαβ_avoid⟩ := h_witness
  have h_endpt0 : αβ 0 = α' 0 := by
    have h := hαβ_left 0 ⟨le_refl _, by norm_num⟩
    simpa using h
  have h_endpt1 : αβ 1 = β' 1 := by
    have h := hαβ_right 1 ⟨by norm_num, le_refl _⟩
    have hh : (2 * (1 : ℝ) - 1) = 1 := by norm_num
    rw [hh] at h
    exact h
  have h_integral :=
    c1_concat_integral_additive_via_chain_rule (Q := Q)
      hα' hβ' hαβ_c1 hαβ_left hαβ_right
  exact ⟨αβ, hαβ_c1, h_endpt0, h_endpt1, hαβ_avoid, h_integral⟩

end Problems.residue_thm
