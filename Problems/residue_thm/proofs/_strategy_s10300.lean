import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_exp_path_integral_eq_one

namespace Problems.residue_thm

-- Reduce integrality of ∫ deriv γ / (γ - a) to: exp(∫) = 1.
-- Sub-goal `exp_path_integral_eq_one` is the analytic core (constant-function
-- argument: d/dt [exp(-G(t))·(γ t - a)] = 0 with G the partial integral, hence
-- exp(-G(1))·(γ 1 - a) = exp(0)·(γ 0 - a) = γ 0 - a, and γ 0 = γ 1 ≠ a forces
-- exp(-G(1)) = 1; sign-swap gives exp(G(1)) = 1 in the statement here).
-- Closer: `Complex.exp_eq_one_iff` extracts the integer n with ∫ = n·(2πI);
-- ring re-associates to `2 π I · n` as the conclusion demands.
theorem s10300
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ∃ k : ℤ, (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a))
          = 2 * Real.pi * Complex.I * k  := by
  have h_exp := exp_path_integral_eq_one hγ hclosed havoid
  obtain ⟨n, hn⟩ := Complex.exp_eq_one_iff.mp h_exp
  exact ⟨n, by rw [hn]; ring⟩

end Problems.residue_thm
