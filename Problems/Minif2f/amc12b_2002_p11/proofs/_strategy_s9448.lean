import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs
import Problems.Minif2f.amc12b_2002_p11.proofs.L_a_ge_five
import Problems.Minif2f.amc12b_2002_p11.proofs.L_a_le_five

namespace Problems.Minif2f.amc12b_2002_p11

-- Squeeze a between two bounds derived from prime triplet constraints.
-- (1) a ≥ 5 rules out a=2,3 (a-2 ∈ {0,1} not prime).
-- (2) a ≤ 5 rules out a ≥ 7 via mod 3 argument (one of a±2 divisible by 3).
theorem s9448 : ∀ (a : ℕ) (h₀ : Nat.Prime a)
    (h₂ : Nat.Prime (a + 2)) (h₃ : Nat.Prime (a - 2)), a = 5  := by
  intro a h₀ h₂ h₃
  have hge : a ≥ 5 := a_ge_five a h₀ h₂ h₃
  have hle : a ≤ 5 := a_le_five a h₀ h₂ h₃
  omega

end Problems.Minif2f.amc12b_2002_p11
