import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c1_concat_piecewise_existence
import Problems.residue_thm.proofs.L_c1_piecewise_concat_integral_split

namespace Problems.residue_thm

-- Decompose: (1) construct a C¹ concat h with explicit piecewise form
--   h t = α' (2*t) on [0, 1/2] and h t = β' (2*t - 1) on [1/2, 1], absorbing
--   the endpoint/avoidance/C¹ obligations into the construction sub-goal
--   (the flat-derivative hypotheses keep deriv continuous across the join);
--   (2) prove integral additivity for any C¹ h with that piecewise form.
-- (1) bundles all structural facts about the witness; (2) reduces the
-- transcendental integral equation to a generic change-of-variable
-- argument that no longer mentions the specific concat construction.
theorem s10547
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
  obtain ⟨h, hh_c1, hh_endpt0, hh_endpt1, hh_avoid, hh_left, hh_right⟩ :=
    c1_concat_piecewise_existence (a := a)
      hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  have h_int :
      (∫ t in (0 : ℝ)..1, Q (h t) * deriv h t) =
        (∫ t in (0 : ℝ)..1, Q (α' t) * deriv α' t) +
        (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t) :=
    c1_piecewise_concat_integral_split (Q := Q) hα' hβ' hh_c1 hh_left hh_right
  exact ⟨h, hh_c1, hh_endpt0, hh_endpt1, hh_avoid, h_int⟩

end Problems.residue_thm
