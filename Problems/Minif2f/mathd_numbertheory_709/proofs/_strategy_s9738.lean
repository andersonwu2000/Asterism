import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_coprime_to_6_div_card_le_one

namespace Problems.Minif2f.mathd_numbertheory_709

-- Reduce to a divisor-counting bound: the set of divisors of n coprime to 6
-- has cardinality ≤ 1. Combined with `1` being trivially in that set, every
-- coprime-to-6 divisor must equal 1.
theorem s9738 : ∀ (n : ℕ) (h₀ : 0 < n)
    (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
    (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
    ∀ m, m ∣ n → Nat.Coprime m 6 → m = 1  := by
  intro n h₀ h₁ h₂ m hm hco
  have h_le := coprime_to_6_div_card_le_one n h₀ h₁ h₂
  have h_one_in : 1 ∈ (Nat.divisors n).filter (fun d => Nat.Coprime d 6) :=
    Finset.mem_filter.mpr ⟨Nat.one_mem_divisors.mpr h₀.ne', Nat.coprime_one_left 6⟩
  have h_m_in : m ∈ (Nat.divisors n).filter (fun d => Nat.Coprime d 6) :=
    Finset.mem_filter.mpr ⟨Nat.mem_divisors.mpr ⟨hm, h₀.ne'⟩, hco⟩
  exact (Finset.card_le_one.mp h_le) m h_m_in 1 h_one_in

end Problems.Minif2f.mathd_numbertheory_709
