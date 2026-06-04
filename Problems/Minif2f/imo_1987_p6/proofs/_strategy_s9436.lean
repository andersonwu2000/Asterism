import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs.L_hyp_yields_p_prime
import Problems.Minif2f.imo_1987_p6.proofs.L_prime_quadratic_extension_assuming_prime

namespace Problems.Minif2f.imo_1987_p6

-- Decompose into two sub-goals: (1) the hypothesis at k=0 forces `Nat.Prime p`,
-- (2) with `Nat.Prime p` in scope, derive the conclusion (this is the IMO core).
-- Sub-goal (1) is a true leaf (instantiate the universal at k=0). Sub-goal (2)
-- is the residual IMO 1987 P6 statement with one extra fact (`p` prime) added.
theorem s9436 : ∀ (p : ℕ),
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.Prime (i^2 + i + p)  := by
  intro p hp
  have h_p_prime : Nat.Prime p := hyp_yields_p_prime p hp
  exact prime_quadratic_extension_assuming_prime p h_p_prime hp

end Problems.Minif2f.imo_1987_p6
