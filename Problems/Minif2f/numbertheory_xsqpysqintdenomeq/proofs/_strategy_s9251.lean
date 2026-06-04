import Mathlib
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.Defs
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.proofs.L_eq_den_of_add_int
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.proofs.L_nat_sq_inj
import Problems.Minif2f.numbertheory_xsqpysqintdenomeq.proofs.L_rat_sq_den

namespace Problems.Minif2f.numbertheory_xsqpysqintdenomeq

-- Use `(q^2).den = q.den^2`, `(a+b).den=1 ⇒ a.den=b.den`, and ℕ-square-injectivity.
-- Squaring lifts each rational's denominator to its square; (x^2+y^2).den = 1 forces
-- x^2.den = y^2.den, hence x.den^2 = y.den^2; nat-square injectivity finishes.
theorem s9251 : ∀ (x y : ℚ) (h₀ : (x ^ 2 + y ^ 2).den = 1), x.den = y.den  := by
  intro x y h₀
  have h_sq_x := rat_sq_den x
  have h_sq_y := rat_sq_den y
  have h_eq := eq_den_of_add_int (x^2) (y^2) h₀
  exact nat_sq_inj x.den y.den (h_sq_x.symm.trans (h_eq.trans h_sq_y))

end Problems.Minif2f.numbertheory_xsqpysqintdenomeq
