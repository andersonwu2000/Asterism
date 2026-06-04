import Mathlib
import Problems.Minif2f.aimeII_2020_p6.Defs
import Problems.Minif2f.aimeII_2020_p6.proofs.L_block_invariant

namespace Problems.Minif2f.aimeII_2020_p6

-- Reduce to a periodic-5 block invariant: for every k, the tuple
-- (t(5k+1), t(5k+2), t(5k+3), t(5k+4), t(5k+5)) equals (20, 21, 53/250, 103/26250, 101/525).
-- Specialize at k = 403 (since 5*403 + 5 = 2020) and project the 5th conjunct.
-- The block_invariant is structurally bigger (induction on k, base case = direct recurrence
-- chain t 3..t 5, step = same recurrence applied to the next block of five) so it goes to
-- Backward; the parent reduction is a mechanical obtain + simpa.
theorem s9393 : ∀ (t : ℕ → ℚ) (h₀ : t 1 = 20) (h₁ : t 2 = 21)
    (h₂ : ∀ n ≥ 3, t n = (5 * t (n - 1) + 1) / (25 * t (n - 2))),
    t 2020 = 101 / 525  := by
  intro t h₀ h₁ h₂
  have h_block_invariant := block_invariant t h₀ h₁ h₂
  obtain ⟨_, _, _, _, h⟩ := h_block_invariant 403
  simpa using h

end Problems.Minif2f.aimeII_2020_p6
