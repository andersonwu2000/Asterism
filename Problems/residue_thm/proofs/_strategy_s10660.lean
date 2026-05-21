import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_concat_piecewise_avoid_wrap
import Problems.residue_thm.proofs.L_concat_piecewise_integral_split_wrap
import Problems.residue_thm.proofs.L_concat_piecewise_smooth_wrap

namespace Problems.residue_thm

-- Use the standard piecewise concat `t ↦ if t ≤ 1/2 then α' (2t) else β' (2t-1)`
-- as the witness; flat-endpoint derivatives (hα'_deriv, hβ'_deriv) + h_match make the
-- glue C¹. Three structural sub-goals capture (smooth, avoid a, integral split);
-- endpoints αβ 0 = α' 0 and αβ 1 = β' 1 reduce by `simp` / `norm_num` on the `if`.
theorem s10660
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
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
  have h_smooth :
      ContDiffOn ℝ 1
        (fun t : ℝ => if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1))
        (Set.Icc 0 1) :=
    concat_piecewise_smooth_wrap hα' hβ' h_match hα'_deriv hβ'_deriv
  have h_avoid :
      ∀ t ∈ Set.Icc (0 : ℝ) 1,
        (fun t : ℝ => if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1)) t ≠ a :=
    concat_piecewise_avoid_wrap hα'_avoid hβ'_avoid
  have h_split :
      (∫ t in (0 : ℝ)..1,
          Q ((fun t : ℝ => if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1)) t) *
            deriv (fun t : ℝ => if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1)) t) =
        (∫ t in (0 : ℝ)..1, Q (α' t) * deriv α' t) +
        (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t) :=
    concat_piecewise_integral_split_wrap (Q := Q) hα' hβ' h_match hα'_deriv hβ'_deriv
  refine ⟨fun t => if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1), h_smooth, ?_, ?_, h_avoid, h_split⟩
  · change (if (0:ℝ) ≤ (1:ℝ)/2 then α' (2*0) else β' (2*0 - 1)) = α' 0
    simp
  · change (if (1:ℝ) ≤ (1:ℝ)/2 then α' (2*1) else β' (2*1 - 1)) = β' 1
    norm_num

end Problems.residue_thm
