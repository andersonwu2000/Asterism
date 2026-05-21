import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_concat_witness_left_eq
import Problems.residue_thm.proofs.L_concat_witness_no_pole
import Problems.residue_thm.proofs.L_concat_witness_right_eq
import Problems.residue_thm.proofs.L_concat_witness_smooth

namespace Problems.residue_thm

-- Pick the explicit piecewise witness αβ t := if t ≤ 1/2 then α'(2t) else β'(2t-1)
-- and discharge the four conjuncts as independent sub-goals: (1) C¹ smoothness
-- of the glue at the junction (the only structurally hard piece — uses the
-- derivative-vanish endpoint conditions on α' / β' plus h_match); (2) the ite
-- collapses to α'(2t) on [0,1/2]; (3) the ite collapses to β'(2t-1) on [1/2,1]
-- (boundary at 1/2 uses h_match); (4) the witness avoids the pole a, by case
-- split on the ite branch and the corresponding avoidance hypothesis.
theorem s10615
    {a : ℂ} {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∃ αβ : ℝ → ℂ,
      ContDiffOn ℝ 1 αβ (Set.Icc 0 1) ∧
      (∀ t ∈ Set.Icc (0 : ℝ) (1/2), αβ t = α' (2*t)) ∧
      (∀ t ∈ Set.Icc (1/2 : ℝ) 1, αβ t = β' (2*t - 1)) ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, αβ t ≠ a)  := by
  have h_smooth := concat_witness_smooth hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  have h_left := concat_witness_left_eq hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  have h_right := concat_witness_right_eq hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  have h_avoid := concat_witness_no_pole hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  refine ⟨fun t => if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1), ?_, ?_, ?_, ?_⟩
  · exact h_smooth
  · exact h_left
  · exact h_right
  · exact h_avoid

end Problems.residue_thm
