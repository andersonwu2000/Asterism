import Mathlib
import Problems.Minif2f.mathd_numbertheory_42.Defs
import Problems.Minif2f.mathd_numbertheory_42.proofs.L_least_eq_eleven
import Problems.Minif2f.mathd_numbertheory_42.proofs.L_second_least_eq_fifty_one

namespace Problems.Minif2f.mathd_numbertheory_42

-- Split into u = 11 and v = 51, then close u + v = 62 by omega.
-- Each sub-goal carries all parent binders so they can extract the
-- least-element data from h₀/h₁/h₂ independently.
theorem s729 : ∀ (S : Set ℕ) (u v : ℕ)
    (h₀ : ∀ a : ℕ, a ∈ S ↔ 0 < a ∧ 27 * a % 40 = 17)
    (h₁ : IsLeast S u) (h₂ : IsLeast (S \ {u}) v), u + v = 62 := by
  intro S u v h₀ h₁ h₂
  have hu := least_eq_eleven S u v h₀ h₁ h₂
  have hv := second_least_eq_fifty_one S u v h₀ h₁ h₂
  omega

end Problems.Minif2f.mathd_numbertheory_42
