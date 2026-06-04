import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs
import Problems.Minif2f.amc12b_2002_p11.proofs.L_force_a_eq_five
import Problems.Minif2f.amc12b_2002_p11.proofs.L_force_b_eq_two

namespace Problems.Minif2f.amc12b_2002_p11

-- Prime constraints force a=5, b=2 (only prime triplet a-2,a,a+2 is 3,5,7;
-- parity forces b=2 since both odd primes sum to even ≥ 6, not prime).
-- Then 5+2+(5-2+(5+2)) = 17, decidably prime.
theorem s593 : ∀ (a b : ℕ) (h₀ : Nat.Prime a) (h₁ : Nat.Prime b)
    (h₂ : Nat.Prime (a + b)) (h₃ : Nat.Prime (a - b)),
    Nat.Prime (a + b + (a - b + (a + b))) := by
  intro a b h₀ h₁ h₂ h₃
  have ha : a = 5 := force_a_eq_five a b h₀ h₁ h₂ h₃
  have hb : b = 2 := force_b_eq_two a b h₀ h₁ h₂ h₃
  subst ha
  subst hb
  decide

end Problems.Minif2f.amc12b_2002_p11
