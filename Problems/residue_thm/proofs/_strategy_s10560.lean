import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_piecewise_concat_witness_avoid
import Problems.residue_thm.proofs.L_piecewise_concat_witness_c1
import Problems.residue_thm.proofs.L_piecewise_concat_witness_right_eq

namespace Problems.residue_thm

-- Construct the C¹ concatenation explicitly as
--   `h t = α' (2t)` on `[0, 1/2]`, `β' (2t - 1)` on `[1/2, 1]`.
-- Strategy splits into 3 sub-goals + 3 inline arithmetic conjuncts: C¹
-- regularity (hardest — leverages the flat-derivative hypotheses at the
-- join), avoidance (pointwise from α'/β' avoidance), and the right-piece
-- equality (needs `h_match` to evaluate the if-branch at the boundary
-- t=1/2). The endpoint values and the left-piece equality reduce to
-- pure `if_pos`/`if_neg` + arithmetic and stay inline in the patch.
theorem s10560
    {a : ℂ} {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∃ h : ℝ → ℂ,
      ContDiffOn ℝ 1 h (Set.Icc 0 1) ∧
      h 0 = α' 0 ∧
      h 1 = β' 1 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, h t ≠ a) ∧
      (∀ t ∈ Set.Icc (0 : ℝ) (1/2), h t = α' (2*t)) ∧
      (∀ t ∈ Set.Icc (1/2 : ℝ) 1, h t = β' (2*t - 1))  := by
  -- Witness: linear reparametrization concatenation
  --   h t = α' (2t) on [0, 1/2], β' (2t - 1) on [1/2, 1].
  -- Decomposition:
  --   (1) `piecewise_concat_witness_c1` — C¹ regularity (flat derivatives
  --       at the join force `deriv` continuity across t=1/2).
  --   (2) `piecewise_concat_witness_avoid` — avoidance follows pointwise
  --       from α'/β' avoidance via the branch eval.
  --   (3) `piecewise_concat_witness_right_eq` — right piece equality
  --       requires `h_match` to handle the boundary t=1/2.
  -- Remaining 3 conjuncts (h 0 = α' 0, h 1 = β' 1, left piece) are pure
  -- definitional / arithmetic and stay inline.
  refine ⟨fun t => if t ≤ 1/2 then α' (2*t) else β' (2*t - 1), ?_, ?_, ?_, ?_, ?_, ?_⟩
  · exact piecewise_concat_witness_c1 hα' hα'_avoid hβ' hβ'_avoid h_match
      hα'_deriv hβ'_deriv
  · change (if (0:ℝ) ≤ 1/2 then α' (2*0) else β' (2*0 - 1)) = α' 0
    rw [if_pos (by norm_num : (0:ℝ) ≤ 1/2)]
    norm_num
  · change (if (1:ℝ) ≤ 1/2 then α' (2*1) else β' (2*1 - 1)) = β' 1
    rw [if_neg (by norm_num : ¬ ((1:ℝ) ≤ 1/2))]
    norm_num
  · exact piecewise_concat_witness_avoid hα' hα'_avoid hβ' hβ'_avoid h_match
      hα'_deriv hβ'_deriv
  · intro t ht
    change (if t ≤ 1/2 then α' (2*t) else β' (2*t - 1)) = α' (2*t)
    rw [if_pos ht.2]
  · exact piecewise_concat_witness_right_eq hα' hα'_avoid hβ' hβ'_avoid h_match
      hα'_deriv hβ'_deriv

end Problems.residue_thm


