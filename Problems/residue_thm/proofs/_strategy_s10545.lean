import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_polar_path_modulus_pos
import Problems.residue_thm.proofs.L_polar_path_smooth

namespace Problems.residue_thm

-- Construct γ(t) = ((1-t) + t·‖w‖) · exp(i·t·arg w) — a C¹ polar interpolation
-- from 1 to w whose modulus stays positive away from 0.
-- Sub-goals: (a) smoothness of the explicit formula, (b) modulus 1-t+t·‖w‖ > 0
-- on Icc 0 1 (since both endpoints 1 and ‖w‖ are positive when w ≠ 0).
-- Endpoint equalities γ(0)=1 and γ(1)=w discharge inline via simp and
-- Complex.norm_mul_exp_arg_mul_I; non-vanishing combines (b) with Complex.exp_ne_zero.
theorem s10545 :
    ∀ w : ℂ, w ≠ 0 → ∃ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) ∧
      γ 0 = 1 ∧ γ 1 = w ∧ (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ 0)  := by
  intro w hw
  refine ⟨fun t : ℝ =>
    (((1 - t + t * ‖w‖ : ℝ) : ℂ)) *
      Complex.exp (((t * Complex.arg w : ℝ) : ℂ) * Complex.I), ?_, ?_, ?_, ?_⟩
  · exact polar_path_smooth w hw
  · -- γ 0 = 1
    show ((1 - 0 + 0 * ‖w‖ : ℝ) : ℂ) * Complex.exp (((0 * Complex.arg w : ℝ) : ℂ) * Complex.I) = 1
    simp
  · -- γ 1 = w
    show ((1 - 1 + 1 * ‖w‖ : ℝ) : ℂ) * Complex.exp (((1 * Complex.arg w : ℝ) : ℂ) * Complex.I) = w
    have h1 : ((1 - 1 + 1 * ‖w‖ : ℝ) : ℂ) = (‖w‖ : ℂ) := by push_cast; ring
    have h2 : ((1 * Complex.arg w : ℝ) : ℂ) = (Complex.arg w : ℂ) := by push_cast; ring
    rw [h1, h2]
    exact Complex.norm_mul_exp_arg_mul_I w
  · intro t ht
    have hpos : (0:ℝ) < 1 - t + t * ‖w‖ := polar_path_modulus_pos w hw t ht
    have hreal_ne : ((1 - t + t * ‖w‖ : ℝ) : ℂ) ≠ 0 := by exact_mod_cast hpos.ne'
    exact mul_ne_zero hreal_ne (Complex.exp_ne_zero _)

end Problems.residue_thm
