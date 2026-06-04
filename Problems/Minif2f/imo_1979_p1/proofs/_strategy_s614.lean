import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs.L_coprime_div_transfer
import Problems.Minif2f.imo_1979_p1.proofs.L_sum_eq_canonical_form

namespace Problems.Minif2f.imo_1979_p1

-- Decompose into: (1) sum equals a/b in canonical form where 1979 ∣ a and
-- gcd(b, 1979) = 1 (the numerical/arithmetic content), and
-- (2) an abstract divisibility-transfer lemma over equal rationals.
theorem s614 : ∀ (p q : ℕ) (h₀ : 0 < q) (h₁ : (∑ k ∈ Finset.Icc (1 : ℕ) 1319, (-1) ^ (k + 1) * ((1 : ℝ) / k)) = p / q), 1979 ∣ p  := by
  intro p q h₀ h₁
  have h_canonical := sum_eq_canonical_form
  obtain ⟨a, b, hb_pos, hb_cop, ha_div, hsum⟩ := h_canonical
  exact coprime_div_transfer p q a b h₀ hb_pos hb_cop ha_div (hsum.symm.trans h₁)

end Problems.Minif2f.imo_1979_p1
