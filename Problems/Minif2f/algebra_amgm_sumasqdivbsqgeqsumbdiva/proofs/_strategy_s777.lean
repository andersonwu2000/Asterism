import Mathlib
import Problems.Minif2f.algebra_amgm_sumasqdivbsqgeqsumbdiva.Defs
import Problems.Minif2f.algebra_amgm_sumasqdivbsqgeqsumbdiva.proofs.L_amgm_two_sq_div

namespace Problems.Minif2f.algebra_amgm_sumasqdivbsqgeqsumbdiva

-- Pairwise AM-GM `x^2/y^2 + y^2/z^2 ≥ 2*(x/z)` applied cyclically over (a,b,c).
-- Summing the three instances gives 2·LHS ≥ 2·RHS, then `linarith` halves.
theorem s777 : ∀ (a b c : ℝ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c), a ^ 2 / b ^ 2 + b ^ 2 / c ^ 2 + c ^ 2 / a ^ 2 ≥ b / a + c / b + a / c  := by
  intro a b c h₀
  obtain ⟨ha, hb, hc⟩ := h₀
  have h1 := amgm_two_sq_div a b c ha hb hc
  have h2 := amgm_two_sq_div b c a hb hc ha
  have h3 := amgm_two_sq_div c a b hc ha hb
  linarith

end Problems.Minif2f.algebra_amgm_sumasqdivbsqgeqsumbdiva
