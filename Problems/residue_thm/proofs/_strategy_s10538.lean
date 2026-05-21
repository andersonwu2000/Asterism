import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c1_concat_flat_endpoints_integral
import Problems.residue_thm.proofs.L_c1_path_smooth_reparam_flat_endpoints

namespace Problems.residue_thm

-- Decompose: (1) reparametrize each input path by `Real.smoothTransition`
-- to obtain matching-endpoint paths whose derivWithin vanishes at the
-- junction-side boundary, preserving the integral; (2) concatenate two
-- C¹ paths whose derivatives vanish at the matching boundary into a single
-- C¹ path with additive integral.
theorem s10538
    {Q : ℂ → ℂ} {a : ℂ}
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
        (∫ t in (0 : ℝ)..1, Q (β t) * deriv β t)  := by
  obtain ⟨α', hα'_c1, hα'_0, hα'_1, _hα'_d0, hα'_d1, hα'_avoid', hα'_int⟩ :=
    c1_path_smooth_reparam_flat_endpoints (Q := Q) (a := a) hα hα_avoid
  obtain ⟨β', hβ'_c1, hβ'_0, hβ'_1, hβ'_d0, _hβ'_d1, hβ'_avoid', hβ'_int⟩ :=
    c1_path_smooth_reparam_flat_endpoints (Q := Q) (a := a) hβ hβ_avoid
  have h_match' : α' 1 = β' 0 := by rw [hα'_1, h_match, ← hβ'_0]
  obtain ⟨αβ, hαβ_c1, hαβ_0, hαβ_1, hαβ_avoid, hαβ_int⟩ :=
    c1_concat_flat_endpoints_integral (Q := Q) (a := a)
      hα'_c1 hα'_avoid' hβ'_c1 hβ'_avoid' h_match' hα'_d1 hβ'_d0

  refine ⟨αβ, hαβ_c1, ?_, ?_, hαβ_avoid, ?_⟩
  · rw [hαβ_0, hα'_0]
  · rw [hαβ_1, hβ'_1]
  · rw [hαβ_int, hα'_int, hβ'_int]


end Problems.residue_thm
