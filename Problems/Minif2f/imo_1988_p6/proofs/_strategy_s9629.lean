import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs
import Problems.Minif2f.imo_1988_p6.proofs.L_equal_case
import Problems.Minif2f.imo_1988_p6.proofs.L_vieta_step

namespace Problems.Minif2f.imo_1988_p6

-- Strong induction on `a` (Nat.strong_induction_on). Dispatch on `b ≤ a`:
-- if b = a, equal_case forces a = 1, k = 1; if b < a, vieta_step either exhibits
-- the square directly or produces an order-preserving Vieta jump (c, d) with c < a,
-- which the strong IH closes.
theorem s9629 : ∀ (a b k : ℕ), 0 < a → 0 < b → b ≤ a →
    a ^ 2 + b ^ 2 = (a * b + 1) * k → ∃ x : ℕ, x ^ 2 = k  := by
  intro a
  induction a using Nat.strong_induction_on with
  | _ a ih =>
    intro b k ha hb hba heq
    rcases lt_or_eq_of_le hba with hlt | hba_eq
    · -- b < a: Vieta-jump, recurse on strictly smaller `c`
      rcases vieta_step a b k ha hb hlt heq with hsq | ⟨c, d, hc, hd, hdc, hca, hcd⟩
      · exact hsq
      · exact ih c hca d k hc hd hdc hcd
    · -- b = a: equal_case forces a = 1, k = 1
      subst hba_eq
      exact equal_case b k hb heq

end Problems.Minif2f.imo_1988_p6
