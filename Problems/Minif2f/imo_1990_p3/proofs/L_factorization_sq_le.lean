import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- factorization_sq_le: n^2 | 2^n+1 implies 2*v_3(n) ≤ v_3(2^n+1)
-- Uses Nat.factorization_le_iff_dvd to lift divisibility to a Finsupp ≤,
-- then Nat.factorization_pow + smul to rewrite (n^2).factorization 3 = 2 * n.factorization 3.
theorem factorization_sq_le :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 →
      2 * n.factorization 3 ≤ (2 ^ n + 1).factorization 3 := by
  intro n hn hdvd
  have hne_sq : n ^ 2 ≠ 0 := by positivity
  have hne_rhs : 2 ^ n + 1 ≠ 0 := by positivity
  have hle : (n ^ 2).factorization ≤ (2 ^ n + 1).factorization :=
    (Nat.factorization_le_iff_dvd hne_sq hne_rhs).mpr hdvd
  have h3 := hle 3
  rw [Nat.factorization_pow, Finsupp.smul_apply, smul_eq_mul] at h3
  linarith

end Problems.Minif2f.imo_1990_p3
