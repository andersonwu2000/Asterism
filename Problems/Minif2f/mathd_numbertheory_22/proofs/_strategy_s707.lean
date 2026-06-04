import Mathlib
import Problems.Minif2f.mathd_numbertheory_22.Defs

namespace Problems.Minif2f.mathd_numbertheory_22

-- Set `k := Nat.sqrt (10*b+6)`, so `h₁ : k*k = 10*b+6`. From `b < 10` we get
-- `10*b+6 ≤ 96 < 100`, hence `k < 10` (else `k*k ≥ 100`). `interval_cases k`
-- splits into ten concrete `k = c` cases; in each, `h₁` becomes `c*c = 10*b+6`,
-- a linear constraint that `omega` resolves (k∈{4,6} ⇒ b∈{1,3}, others ⇒ ⊥).
-- Kernel-only — no `native_decide`, no rogue axioms.
theorem s707 : ∀ (b : ℕ) (h₀ : b < 10) (h₁ : Nat.sqrt (10 * b + 6) * Nat.sqrt (10 * b + 6) = 10 * b + 6), b = 3 ∨ b = 1  := by
  intro b h₀ h₁
  set k := Nat.sqrt (10 * b + 6) with hk_def
  have hk_lt : k < 10 := by
    rcases Nat.lt_or_ge k 10 with h | h
    · exact h
    · exfalso
      have h10 : 10 * 10 ≤ k * k := Nat.mul_le_mul h h
      rw [h₁] at h10
      omega
  interval_cases k <;> omega

end Problems.Minif2f.mathd_numbertheory_22
