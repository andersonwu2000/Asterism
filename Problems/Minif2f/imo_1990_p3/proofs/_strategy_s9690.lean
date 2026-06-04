import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_lte_three_lower_dvd
import Problems.Minif2f.imo_1990_p3.proofs.L_lte_three_upper_not_dvd

namespace Problems.Minif2f.imo_1990_p3

-- Pin v_3(2^n+1) exactly via a two-sided pow-divisibility sandwich.
-- Lower: 3^(1+v_3(n)) ∣ 2^n+1.  Upper: ¬ 3^(2+v_3(n)) ∣ 2^n+1.
-- Combine via `Nat.Prime.pow_dvd_iff_le_factorization` (for p=3, n≠0):
--   lower gives 1+v_3(n) ≤ v_3(2^n+1); upper rules out ≥ 2+v_3(n);
--   omega closes equality.
theorem s9690 :
    ∀ (n : ℕ), 2 ≤ n → Odd n → 3 ∣ n →
      (2^n + 1).factorization 3 = 1 + n.factorization 3  := by
  intro n hn hodd hdvd
  have h_lower : 3^(1 + n.factorization 3) ∣ (2^n + 1) :=
    lte_three_lower_dvd n hn hodd hdvd
  have h_upper : ¬ 3^(2 + n.factorization 3) ∣ (2^n + 1) :=
    lte_three_upper_not_dvd n hn hodd hdvd
  have h3 : Nat.Prime 3 := by decide
  have hne : (2^n + 1) ≠ 0 := by positivity
  have hge : 1 + n.factorization 3 ≤ (2^n + 1).factorization 3 :=
    (h3.pow_dvd_iff_le_factorization hne).mp h_lower
  have hlt : (2^n + 1).factorization 3 < 2 + n.factorization 3 := by
    by_contra hge2
    exact h_upper ((h3.pow_dvd_iff_le_factorization hne).mpr (by omega))
  omega

end Problems.Minif2f.imo_1990_p3
