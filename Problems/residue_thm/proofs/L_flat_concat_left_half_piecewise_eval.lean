import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- flat_concat_left_half_piecewise_eval: piecewise trivially true on [0,1/2]; substitution + FTC
-- gives α' 1 - α' 0.
theorem flat_concat_left_half_piecewise_eval
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    (∫ s in (0:ℝ)..((1:ℝ)/2),
      (if s ≤ (1:ℝ)/2
        then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
      = α' 1 - α' 0 := by
  have h1 : ∫ s in (0:ℝ)..(1/2),
      (if s ≤ (1:ℝ)/2 then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
       else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) =
    ∫ s in (0:ℝ)..(1/2), 2 * derivWithin α' (Set.Icc 0 1) (2*s) := by
    apply intervalIntegral.integral_congr
    intro s hs
    simp only [Set.uIcc_of_le (by norm_num : (0:ℝ) ≤ 1/2), Set.mem_Icc] at hs
    dsimp only
    rw [if_pos hs.2]
  rw [h1]
  -- Pull out constant 2 (as ℂ-scalar); provide f explicitly for unification
  have h2 : ∫ s in (0:ℝ)..(1/2), 2 * derivWithin α' (Set.Icc 0 1) (2 * s) =
      2 * ∫ s in (0:ℝ)..(1/2), derivWithin α' (Set.Icc 0 1) (2 * s) :=
    intervalIntegral.integral_const_mul 2 (fun s => derivWithin α' (Set.Icc 0 1) (2 * s))
  rw [h2]
  -- Change of variables u = 2s: ∫ 0..1/2, f(2s) = 2⁻¹ • ∫ 0..1, f(s)
  have h3 : ∫ s in (0:ℝ)..(1/2), derivWithin α' (Set.Icc 0 1) (2 * s) =
      (2:ℝ)⁻¹ • ∫ s in (0:ℝ)..(1:ℝ), derivWithin α' (Set.Icc 0 1) s := by
    have key : ∫ s in (0:ℝ)..(1/2), derivWithin α' (Set.Icc 0 1) (2 * s) =
        (2:ℝ)⁻¹ • ∫ s in (2:ℝ)*0..(2:ℝ)*(1/2), derivWithin α' (Set.Icc 0 1) s :=
      intervalIntegral.integral_comp_mul_left
        (derivWithin α' (Set.Icc 0 1)) (two_ne_zero' ℝ)
    simp only [mul_zero, show (2:ℝ) * (1/2) = 1 from by norm_num] at key
    exact key
  rw [h3, intervalIntegral.integral_derivWithin_Icc_of_contDiffOn_Icc hα' zero_le_one]
  -- Simplify 2 * (2⁻¹ • v) = v in ℂ
  rw [Complex.real_smul]
  push_cast
  field_simp

end Problems.residue_thm
