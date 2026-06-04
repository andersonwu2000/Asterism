import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs
import Problems.Minif2f.amc12b_2002_p11.proofs.L_odd_b_contradiction

namespace Problems.Minif2f.amc12b_2002_p11

-- Case-split on `b` via `Nat.Prime.eq_two_or_odd`: either b = 2 (done), or b is odd.
-- The odd case is delegated to `odd_b_contradiction`, which uses the parity
-- constraint plus the four prime hypotheses to derive False.
theorem s9327 : ∀ (a b : ℕ) (h₀ : Nat.Prime a) (h₁ : Nat.Prime b)
    (h₂ : Nat.Prime (a + b)) (h₃ : Nat.Prime (a - b)), b = 2  := by
  intro a b h₀ h₁ h₂ h₃
  rcases h₁.eq_two_or_odd with hb | hb
  · exact hb
  · exact (odd_b_contradiction a b h₀ h₁ h₂ h₃ hb).elim

end Problems.Minif2f.amc12b_2002_p11
