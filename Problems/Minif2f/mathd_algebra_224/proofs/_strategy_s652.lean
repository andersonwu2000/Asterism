import Mathlib
import Problems.Minif2f.mathd_algebra_224.Defs
import Problems.Minif2f.mathd_algebra_224.proofs.L_sqrt_bound_char

namespace Problems.Minif2f.mathd_algebra_224

-- Show S equals the explicit set {5,6,7,8,9,10,11,12} by characterizing the
-- Real.sqrt bound on naturals, then compute the cardinality of the literal.
theorem s652 : ∀ (S : Finset ℕ) (h₀ : ∀ n : ℕ, n ∈ S ↔ Real.sqrt n < 7 / 2 ∧ 2 < Real.sqrt n), S.card = 8  := by
  intro S h₀
  have h_char := sqrt_bound_char
  have hset : S = ({5,6,7,8,9,10,11,12} : Finset ℕ) := by
    apply Finset.ext
    intro n
    rw [h₀ n]
    exact h_char n
  rw [hset]
  decide

end Problems.Minif2f.mathd_algebra_224
