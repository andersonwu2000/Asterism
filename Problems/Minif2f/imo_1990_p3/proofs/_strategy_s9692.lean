import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_factorization_three_eq_one
import Problems.Minif2f.imo_1990_p3.proofs.L_m_eq_three_pow_factorization

namespace Problems.Minif2f.imo_1990_p3

-- Reduce `m = 3` to: (a) `m` is a pure power of 3, and (b) the 3-adic valuation is exactly 1.
-- (a) `m_eq_three_pow_factorization`: every prime factor of `m` must be 3 (Odd ⇒ no 2;
--     hypothesis ⇒ no prime ≥ 5; 3 is the only prime in [3,5)), so `m = 3 ^ v₃(m)`.
-- (b) `factorization_three_eq_one`: `3 ∣ m` gives `1 ≤ v₃(m)`; `¬ 9 ∣ m` gives `v₃(m) < 2`.
-- Substituting (b) into (a) yields `m = 3 ^ 1 = 3`.
theorem s9692 :
    ∀ (m : ℕ), 2 ≤ m → Odd m → 3 ∣ m → ¬ (9 ∣ m) →
      (∀ p, Nat.Prime p → 5 ≤ p → ¬ p ∣ m) → m = 3  := by
  intro m hm hodd h3 h9 hno
  have h_eq_pow := m_eq_three_pow_factorization m hm hodd h3 h9 hno
  have h_fact := factorization_three_eq_one m hm hodd h3 h9 hno
  rw [h_fact, pow_one] at h_eq_pow
  exact h_eq_pow
end Problems.Minif2f.imo_1990_p3
