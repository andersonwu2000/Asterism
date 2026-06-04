import Mathlib
import Problems.Minif2f.imo_1988_p6.Defs
import Problems.Minif2f.imo_1988_p6.proofs.L_lift_quot_eq
import Problems.Minif2f.imo_1988_p6.proofs.L_vieta_jumping_nat

namespace Problems.Minif2f.imo_1988_p6

-- Split into ℕ-level Vieta-jumping perfect-square claim + a pure cast/division lift.
-- `vieta_jumping_nat`: substantive number-theoretic core, stated in ℕ (no real division).
-- `lift_quot_eq`: mechanical — from the ℕ multiplicative identity, derive the ℝ equality.
set_option linter.style.longLine false in
theorem s618 : ∀ (a b : ℕ) (h₀ : 0 < a ∧ 0 < b) (h₁ : a * b + 1 ∣ a ^ 2 + b ^ 2), ∃ x : ℕ, (x ^ 2 : ℝ) = (a ^ 2 + b ^ 2) / (a * b + 1)  := by
  intro a b h₀ h₁
  obtain ⟨x, hx⟩ := vieta_jumping_nat a b h₀ h₁
  exact ⟨x, lift_quot_eq a b h₀ h₁ x hx⟩

end Problems.Minif2f.imo_1988_p6
