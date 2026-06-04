import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs
import Problems.Minif2f.imo_1988_p6.proofs.L_vieta_a_le_kb
import Problems.Minif2f.imo_1988_p6.proofs.L_vieta_descent_aux_eq
import Problems.Minif2f.imo_1988_p6.proofs.L_vieta_descent_aux_le

namespace Problems.Minif2f.imo_1988_p6

-- Construct the Vieta conjugate a' := k*b - a in ℕ.
-- Three sub-goals: (i) a ≤ k*b so ℕ subtraction agrees with ℤ;
-- (ii) the descent bound k*b - a ≤ b; (iii) the rewritten identity
-- b² + a'² = (b*a' + 1)*k. Pack the trio into the ⟨witness, le, eq⟩ triple.
theorem s9711 : ∀ (a b k : ℕ), 0 < a → 0 < b → b < a →
    a^2 + b^2 = (a*b + 1) * k →
    ∃ a' : ℕ, a' ≤ b ∧ b^2 + a'^2 = (b*a' + 1) * k  := by
  intro a b k ha hb hba heq
  have h_ge : a ≤ k * b := vieta_a_le_kb a b k ha hb hba heq
  have h_le : k * b - a ≤ b := vieta_descent_aux_le a b k ha hb hba heq h_ge
  have h_eq : b^2 + (k*b - a)^2 = (b * (k*b - a) + 1) * k :=
    vieta_descent_aux_eq a b k ha hb hba heq h_ge
  exact ⟨k * b - a, h_le, h_eq⟩
end Problems.Minif2f.imo_1988_p6
