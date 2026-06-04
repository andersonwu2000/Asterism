import Mathlib
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.Defs
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.proofs.L_amgm_real_prod_one

namespace Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn

-- Coerce NNReal → ℝ and reduce to the Real-valued AM-GM with prod=1.
-- Sub-goal `amgm_real_prod_one` abstracts AM-GM on nonneg reals.
theorem s9276 : ∀ (a : ℕ → NNReal) (n : ℕ) (h₀ : Finset.prod (Finset.range n) a = 1), Finset.sum (Finset.range n) a ≥ n  := by
  intro a n h₀
  have h_nonneg : ∀ i ∈ Finset.range n, 0 ≤ ((a i : ℝ)) := by
    intro i _; exact (a i).coe_nonneg
  have h_prod : Finset.prod (Finset.range n) (fun i => ((a i : ℝ))) = 1 := by
    exact_mod_cast h₀
  have h_amgm : (n : ℝ) ≤ Finset.sum (Finset.range n) (fun i => ((a i : ℝ))) :=
    amgm_real_prod_one (fun i => ((a i : ℝ))) n h_nonneg h_prod
  have h_sum_eq :
      Finset.sum (Finset.range n) (fun i => ((a i : ℝ)))
        = ((Finset.sum (Finset.range n) a : NNReal) : ℝ) := by
    push_cast; rfl
  rw [h_sum_eq] at h_amgm
  exact_mod_cast h_amgm

end Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn
