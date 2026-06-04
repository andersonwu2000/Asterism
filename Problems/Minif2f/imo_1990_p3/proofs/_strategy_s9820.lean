import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_cube_factor_2
import Problems.Minif2f.imo_1990_p3.proofs.L_nine_not_dvd_quad
import Problems.Minif2f.imo_1990_p3.proofs.L_three_dvd_quad_2

namespace Problems.Minif2f.imo_1990_p3

-- Decompose `cube_lte_upper` via `a^3+1 = (a+1)(a^2-a+1)` and 3-adic valuation:
-- v_3(a+1) ≤ k+1 (from ¬3^(k+2) ∣ a+1) and v_3(a^2-a+1) = 1 (from `three_dvd_quad_2`
-- + new `nine_not_dvd_quad`) force v_3(a^3+1) ≤ k+2, contradicting 3^(k+3) ∣ a^3+1.
-- Sub-goals: re-use existing `cube_factor_2`, `three_dvd_quad_2`; introduce
-- `nine_not_dvd_quad`: `3 ∣ a+1` ⟹ `¬ 9 ∣ a^2-a+1` (since `a²-a+1 = 3(3k²-3k+1)`).
theorem s9820 :
    ∀ (a k : ℕ), 1 ≤ a → 3 ^ (k + 1) ∣ a + 1 → ¬ 3 ^ (k + 2) ∣ a + 1 →
      ¬ 3 ^ (k + 3) ∣ a^3 + 1  := by
  intro a k ha hk hnk hcontra
  have h_cube_factor : a^3 + 1 = (a + 1) * (a^2 - a + 1) := cube_factor_2 a ha
  have h3 : (3:ℕ) ∣ a + 1 := dvd_trans (dvd_pow_self 3 (Nat.succ_ne_zero k)) hk
  have h_three_dvd_quad : (3:ℕ) ∣ a^2 - a + 1 := three_dvd_quad_2 a h3
  have h_nine_not_dvd_quad : ¬ (9:ℕ) ∣ a^2 - a + 1 := nine_not_dvd_quad a ha h3
  have hap1_ne : a + 1 ≠ 0 := by omega
  have hle : a ≤ a^2 := by nlinarith
  have hquad_ne : a^2 - a + 1 ≠ 0 := by omega
  have hcube_ne : a^3 + 1 ≠ 0 := by positivity
  have hap1_le : (a + 1).factorization 3 ≤ k + 1 := by
    by_contra hgt
    push_neg at hgt
    apply hnk
    rw [Nat.Prime.pow_dvd_iff_le_factorization Nat.prime_three hap1_ne]
    omega
  have hquad_fac : (a^2 - a + 1).factorization 3 = 1 := by
    have hge : 1 ≤ (a^2 - a + 1).factorization 3 := by
      rw [← Nat.Prime.pow_dvd_iff_le_factorization Nat.prime_three hquad_ne]
      simpa using h_three_dvd_quad
    have hlt : (a^2 - a + 1).factorization 3 < 2 := by
      by_contra hge2
      push_neg at hge2
      apply h_nine_not_dvd_quad
      rw [show (9 : ℕ) = 3 ^ 2 by norm_num]
      rw [Nat.Prime.pow_dvd_iff_le_factorization Nat.prime_three hquad_ne]
      exact hge2
    omega
  have hcube_le : (a^3 + 1).factorization 3 ≤ k + 2 := by
    rw [h_cube_factor, Nat.factorization_mul hap1_ne hquad_ne]
    simp only [Finsupp.coe_add, Pi.add_apply]
    rw [hquad_fac]
    omega
  have hcube_ge : k + 3 ≤ (a^3 + 1).factorization 3 := by
    rw [← Nat.Prime.pow_dvd_iff_le_factorization Nat.prime_three hcube_ne]
    exact hcontra
  omega

end Problems.Minif2f.imo_1990_p3
