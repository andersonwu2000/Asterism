import Mathlib
import Problems.Minif2f.mathd_numbertheory_13.Defs
import Problems.Minif2f.mathd_numbertheory_13.proofs.L_u_ge_39
import Problems.Minif2f.mathd_numbertheory_13.proofs.L_u_le_39

namespace Problems.Minif2f.mathd_numbertheory_13

-- Antisymmetry: u = 39 ⇐ (u ≤ 39) ∧ (39 ≤ u), combined by `omega`.
-- Sub 1 (u_le_39): 39 ∈ S (since 14*39 % 100 = 46), so IsLeast gives u ≤ 39.
-- Sub 2 (u_ge_39): u ∈ S so 0 < u and 14*u%100=46; rule out u<39 by case analysis.
theorem s9391 : ∀ (u v : ℕ) (S : Set ℕ) (_ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ 14 * n % 100 = 46) (_ : IsLeast S u) (_ : IsLeast (S \ {u}) v), u = 39  := by
  intro u v S h₀ h₁ h₂
  have h_le := u_le_39 u v S h₀ h₁ h₂
  have h_ge := u_ge_39 u v S h₀ h₁ h₂
  omega

end Problems.Minif2f.mathd_numbertheory_13
