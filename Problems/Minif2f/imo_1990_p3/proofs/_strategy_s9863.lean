import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_min_fac_div_three_eq_seven

namespace Problems.Minif2f.imo_1990_p3

-- Decompose by reducing False to a contradiction with `¬ 7 ∣ m`.
-- Sub-goal `min_fac_div_three_eq_seven` shows `Nat.minFac (m/3) = 7` from the
-- `(2 : ZMod q)^6 = 1` hypothesis (q ∣ 63, q prime ≥ 5 ⇒ q = 7). Combinator:
-- `Nat.minFac_dvd` lifts 7 ∣ m/3 to 7 ∣ m via `m = 3*(m/3)`, contradicting h7m.
theorem s9863 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      (2 : ZMod (Nat.minFac (m / 3)))^6 = 1 →
      False  := by
  intro m hm2 hdvd h3m h9m h7m p hp h5p h7p hpm hpow6
  have hq7 : Nat.minFac (m / 3) = 7 :=
    min_fac_div_three_eq_seven m hm2 hdvd h3m h9m h7m p hp h5p h7p hpm hpow6
  have hminFac : Nat.minFac (m / 3) ∣ m / 3 := Nat.minFac_dvd _
  rw [hq7] at hminFac
  have h3m_eq : m = 3 * (m / 3) := by omega
  have h7dvd_m : 7 ∣ m := by rw [h3m_eq]; exact hminFac.mul_left 3
  exact h7m h7dvd_m

end Problems.Minif2f.imo_1990_p3
