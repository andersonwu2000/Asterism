import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_fubini_swap_circle_path
import Problems.residue_thm.proofs.L_inner_path_int_eq_neg_two_pi_i_winding
import Problems.residue_thm.proofs.L_pointwise_sub_cauchy_repr

namespace Problems.residue_thm

-- Pointwise Cauchy substitution + Fubini swap + winding identification.
--   (1) `pointwise_sub_cauchy_repr` — rewrite P(γt)·γ'(t) via hP_repr at z = γ t.
--   (2) `fubini_swap_circle_path` — swap order of ∫₀¹ and ∮ over C(a,ε) (Fubini).
--   (3) `inner_path_int_eq_neg_two_pi_i_winding` — for w on sphere a ε,
--       ∫₀¹ γ'(t)/(w-γt) dt = -(2πi)·windingNumber γ a (sign flip + winding constancy on disk).
theorem s10468
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_repr : ∀ z : ℂ, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), P w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    {ε : ℝ} (hε_pos : 0 < ε)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t)
      = (Complex.windingNumber γ a : ℂ) * (∮ w in C(a, ε), P w) := by
  have h_point := pointwise_sub_cauchy_repr hP hP_tendsto hP_repr hγ h_avoid hclosed hε_pos hε_sep
  have h_fubini := fubini_swap_circle_path hP hP_tendsto hP_repr hγ h_avoid hclosed hε_pos hε_sep
  have h_inner := inner_path_int_eq_neg_two_pi_i_winding hP hP_tendsto hP_repr hγ h_avoid hclosed hε_pos hε_sep
  -- Step 1: substitute pointwise
  have h_int_eq : (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t)
        = ∫ t in (0:ℝ)..1, -((2 * (Real.pi : ℂ) * Complex.I)⁻¹)
                            * (deriv γ t * (∮ w in C(a, ε), P w / (w - γ t))) := by
    apply intervalIntegral.integral_congr
    intro t ht
    rw [Set.uIcc_of_le (by norm_num : (0:ℝ) ≤ 1)] at ht
    change P (γ t) * deriv γ t = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹)
                            * (deriv γ t * (∮ w in C(a, ε), P w / (w - γ t)))
    rw [h_point t ht]; ring
  have h_const_pull :
      (∫ t in (0:ℝ)..1, -((2 * (Real.pi : ℂ) * Complex.I)⁻¹)
                            * (deriv γ t * (∮ w in C(a, ε), P w / (w - γ t))))
        = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹)
            * ∫ t in (0:ℝ)..1, deriv γ t * (∮ w in C(a, ε), P w / (w - γ t)) :=
    intervalIntegral.integral_const_mul _ _
  rw [h_int_eq, h_const_pull, h_fubini]
  -- Step 2: identify inner path integral with winding
  have hcong :
      (∮ w in C(a, ε), P w * (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t)))
        = ∮ w in C(a, ε),
            (-(2 * (Real.pi : ℂ) * Complex.I) * (Complex.windingNumber γ a : ℂ)) * P w := by
    refine circleIntegral.integral_congr hε_pos.le ?_
    intro w hw
    change P w * (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t))
          = (-(2 * (Real.pi : ℂ) * Complex.I) * (Complex.windingNumber γ a : ℂ)) * P w
    rw [h_inner w hw]; ring
  rw [hcong, circleIntegral.integral_const_mul]
  have h_ne : (2 * (Real.pi : ℂ) * Complex.I) ≠ 0 := by
    have hpi : (Real.pi : ℂ) ≠ 0 := by exact_mod_cast Real.pi_ne_zero
    exact mul_ne_zero (mul_ne_zero (by norm_num) hpi) Complex.I_ne_zero
  field_simp

end Problems.residue_thm
