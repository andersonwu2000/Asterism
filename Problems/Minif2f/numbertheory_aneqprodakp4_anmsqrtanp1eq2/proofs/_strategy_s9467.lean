import Mathlib
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.Defs
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.proofs.L_seq_pos

namespace Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2

-- Decompose `a n ≥ 2` (for n ≥ 1) into the universal claim `0 < a n`.
-- Combinator: write n = m+1, apply h₁ so a (m+1) = (∏ k ∈ range (m+1), a k) + 4;
-- positivity of every factor gives the product > 0 via `Finset.prod_pos`, then linarith
-- closes prod + 4 ≥ 2.
theorem s9467 : ∀ (a : ℕ → ℝ) (h₀ : a 0 = 1)
    (h₁ : ∀ n, a (n + 1) = (∏ k ∈ Finset.range (n + 1), a k) + 4)
    (n : ℕ) (_hn : n ≥ 1), a n ≥ 2  := by
  intro a h₀ h₁ n hn
  have h_pos := seq_pos a h₀ h₁
  rcases n with _ | m
  · omega
  · rw [h₁]
    have hp : 0 < ∏ k ∈ Finset.range (m + 1), a k :=
      Finset.prod_pos (fun k _ => h_pos k)
    linarith

end Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2
