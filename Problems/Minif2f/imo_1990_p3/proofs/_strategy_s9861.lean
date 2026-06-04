import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_kernel_two_pow_six_eq_one_q
import Problems.Minif2f.imo_1990_p3.proofs.L_not_two_pow_six_eq_one_q

namespace Problems.Minif2f.imo_1990_p3

-- Decompose ¬ 3 ∣ (minFac(m/3) - 1) by contradiction; assume 3 ∣ q-1.
-- (A) `kernel_two_pow_six_eq_one_q`: 3∣q-1 + 9∤m + odd m + Fermat ⇒ orderOf(2 mod q) ∣ 6.
-- (B) `not_two_pow_six_eq_one_q`: 2^6=1 in ZMod q ⇒ q∣63 ⇒ q=7 (q prime ≥5), but ¬7∣m.
theorem s9861 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      ¬ 3 ∣ (Nat.minFac (m / 3) - 1)  := by
  intro m hm hdvd h3m h9m h7m p hp h5p hp7 hpm h3
  have h_kernel := kernel_two_pow_six_eq_one_q m hm hdvd h3m h9m h7m p hp h5p hp7 hpm h3
  exact not_two_pow_six_eq_one_q m hm hdvd h3m h9m h7m p hp h5p hp7 hpm h_kernel

end Problems.Minif2f.imo_1990_p3
