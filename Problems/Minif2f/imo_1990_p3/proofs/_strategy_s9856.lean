import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_coprime_m_q_pred_from_not_three
import Problems.Minif2f.imo_1990_p3.proofs.L_not_three_dvd_q_sub_one

namespace Problems.Minif2f.imo_1990_p3

-- Reduce to two sub-goals: (1) the kernel `¬ 3 ∣ (minFac(m/3) - 1)` (uses the full
-- orderOf/Fermat chain), and (2) a Builder-level case analysis showing that given
-- `¬ 3 ∣ q-1`, any prime r ∣ gcd(m, q-1) must satisfy r ≠ 3 hence r ∣ m/3 (Euclid),
-- forcing r ≥ minFac(m/3) = q while r ∣ q-1 ⇒ r ≤ q-1; contradiction.
theorem s9856 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      Nat.Coprime m (Nat.minFac (m / 3) - 1)  := by
  intro m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  have h_not3 :=
    not_three_dvd_q_sub_one m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  exact
    coprime_m_q_pred_from_not_three m hm hpow h3 h9 h7 p hp h5 hp7 hpm h_not3

end Problems.Minif2f.imo_1990_p3
