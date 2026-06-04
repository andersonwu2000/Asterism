import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_factorization_sq_le
import Problems.Minif2f.imo_1990_p3.proofs.L_lte_three_step

namespace Problems.Minif2f.imo_1990_p3

-- Two-step LTE-style decomposition.
-- (A) `lte_three_step`: 3-adic valuation identity v_3(2^n+1) = 1 + v_3(n) for odd n with 3 ∣ n.
-- (B) `factorization_sq_le`: from n² ∣ 2^n+1, get 2·v_3(n) ≤ v_3(2^n+1)
--     (squared-divisibility bound on the 3-adic valuation).
-- Combine: 9 ∣ n forces v_3(n) ≥ 2, but (A)+(B) give 2·v_3(n) ≤ 1 + v_3(n), so v_3(n) ≤ 1. omega.
theorem s9646 :
    ∀ (n : ℕ), 2 ≤ n → Odd n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n)  := by
  intro n hn hodd hdvd h3 h9
  have h_lte : (2^n + 1).factorization 3 = 1 + n.factorization 3 :=
    lte_three_step n hn hodd h3
  have h_bound : 2 * n.factorization 3 ≤ (2^n + 1).factorization 3 :=
    factorization_sq_le n hn hdvd
  have h_n_ne : n ≠ 0 := by omega
  have hp3 : Nat.Prime 3 := by decide
  have h32 : (3:ℕ)^2 ∣ n := by
    have heq : (9 : ℕ) = 3^2 := by norm_num
    rw [heq] at h9
    exact h9
  have h_v3_ge : 2 ≤ n.factorization 3 :=
    (Nat.Prime.pow_dvd_iff_le_factorization hp3 h_n_ne).mp h32
  omega

end Problems.Minif2f.imo_1990_p3
