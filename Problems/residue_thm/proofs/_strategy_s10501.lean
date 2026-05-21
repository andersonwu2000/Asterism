import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_inner_cauchy_part_path_int_zero_residue_zero
import Problems.residue_thm.proofs.L_q_eq_inner_cauchy_principal_part

namespace Problems.residue_thm

-- (1) `q_eq_inner_cauchy_principal_part` applies `principal_part_extraction_at_singularity`
--     to the lone pole `a`, yielding a principal part `P` analytic on `ℂ\{a}` with
--     decay at ∞ and an inner-Cauchy-integral representation. Liouville on the entire
--     extension of `Q - P` (regular remainder vanishes at ∞) collapses to `Q = P`
--     globally on `ℂ\{a}`.
-- (2) `inner_cauchy_part_path_int_zero_residue_zero` integrates the Cauchy-integral
--     form of `P` along `γ`: Fubini-swap with the inner circle, the inner
--     `∫₀¹ γ'(t)/(w-γ t) dt` factors through `windingNumber γ w` which is constant on
--     `ball a ε` (γ stays away from a), reducing to `windingNumber γ a · ∮_C(a,ε) Q`;
--     `circle_int_eq_two_pi_residue` evaluates the circle integral to
--     `2πi · residue Q a`, which is `0` by `hQ_res`.
-- Conclude `∫_γ Q = ∫_γ P = 0` via `intervalIntegral.integral_congr`.
theorem s10501
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0))
    (hQ_res : Complex.residue Q a = 0)
    (γ : ℝ → ℂ)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0 := by
  obtain ⟨P, R, hR, hPan, hPtend, hPrep, hQeqP⟩ :=
    q_eq_inner_cauchy_principal_part hQ_an hQ_decay
  have hcong : ∀ t ∈ Set.uIcc (0:ℝ) 1,
      Q (γ t) * deriv γ t = P (γ t) * deriv γ t := by
    intro t ht
    rw [Set.uIcc_of_le zero_le_one] at ht
    have hγt : γ t ∈ Set.univ \ ({a} : Set ℂ) :=
      ⟨trivial, h_avoid t ht⟩
    rw [hQeqP (γ t) hγt]
  rw [intervalIntegral.integral_congr hcong]
  exact inner_cauchy_part_path_int_zero_residue_zero
    hR hQ_an hPan hPtend hPrep hQ_res hγ h_avoid hclosed

end Problems.residue_thm
