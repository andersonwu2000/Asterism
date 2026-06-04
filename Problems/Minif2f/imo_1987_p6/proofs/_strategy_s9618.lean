import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs.L_prime_quadratic_step

namespace Problems.Minif2f.imo_1987_p6

-- Wrap the parent in strong induction on `i`; the residual inductive step
-- (the IMO core) is shipped as a single Backward sub-goal that takes the
-- strong IH `∀ m < i, m ≤ p-2 → Nat.Prime (m^2+m+p)` as an extra premise.
-- This isolates the substantive arithmetic argument from the structural
-- recursion, which is the standard reduction for IMO 1987 P6 and is
-- strictly simpler than the parent (one fewer ∀ and a richer hypothesis).
theorem s9618 : ∀ (p : ℕ),
    Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.Prime (i^2 + i + p)  := by
  intro p hp hk i
  induction i using Nat.strong_induction_on with
  | _ i ih =>
    intro hi
    exact prime_quadratic_step p hp hk i hi ih

end Problems.Minif2f.imo_1987_p6
