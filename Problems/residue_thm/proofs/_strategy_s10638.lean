-- Decompose into THREE sub-goals over the EXPLICIT piecewise concat
--   αβ t := if t ≤ 1/2 then α' (2*t) else β' (2*t - 1)
-- (a) `c1_concat_piecewise_smooth`: ContDiffOn ℝ 1 αβ (Icc 0 1) using the
--     flat-derivative hypotheses to glue across t = 1/2 (matching α'(1) = β'(0)
--     and `derivWithin α' _ 1 = 0 = derivWithin β' _ 0` make derivWithin
--     of the gluing continuous at the join);
-- (b) `c1_concat_piecewise_avoid`: avoidance preserved by pointwise case-split;
-- (c) `c1_concat_piecewise_integral_split`: ∫ Q(αβ)·deriv αβ = ∫ Q(α')·α'' +
--     ∫ Q(β')·β'' via u-substitution on each half (deriv αβ on (0, 1/2) equals
--     `2 · deriv α' (2t)`; symmetric on (1/2, 1)).
-- The endpoint values αβ 0 = α' 0 and αβ 1 = β' 1 are discharged inline by
-- `if_pos` / `if_neg`.
-- The flat-endpoint hypotheses
--   `derivWithin α' (Icc 0 1) 1 = 0`  and  `derivWithin β' (Icc 0 1) 0 = 0`
-- are in scope for both (a) and (c), evading the prior `c1_piecewise_concat_-
-- integral_split` counterexample (α'=t, β'=1+t — which has NON-zero endpoint
-- derivatives, hence does not satisfy our hypotheses).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c1_concat_piecewise_avoid
import Problems.residue_thm.proofs.L_c1_concat_piecewise_integral_split
import Problems.residue_thm.proofs.L_c1_concat_piecewise_smooth

namespace Problems.residue_thm

theorem s10638
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
  refine ⟨fun t => if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1),
    c1_concat_piecewise_smooth hα' hβ' h_match hα'_deriv hβ'_deriv,
    ?_, ?_,
    c1_concat_piecewise_avoid hα'_avoid hβ'_avoid,
    c1_concat_piecewise_integral_split hα' hβ' h_match hα'_deriv hβ'_deriv⟩
  · change (if (0:ℝ) ≤ 1/2 then α' (2*0) else β' (2*0 - 1)) = α' 0
    rw [if_pos (by norm_num : (0:ℝ) ≤ 1/2)]; norm_num
  · change (if (1:ℝ) ≤ 1/2 then α' (2*1) else β' (2*1 - 1)) = β' 1
    rw [if_neg (by norm_num : ¬ ((1:ℝ) ≤ 1/2))]; norm_num

end Problems.residue_thm
