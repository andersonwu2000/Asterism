import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- min_fac_dvd_three_of_two_sq_eq_one: CharP.cast_eq_zero_iff bridges (3 : ZMod p) = 0 to p ∣ 3
-- linear_combination h2sq proves (3 : ZMod p) = 0 from 2^2 = 1 (since 2^2 - 1 = 3)
theorem min_fac_dvd_three_of_two_sq_eq_one :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 →
      Nat.Coprime n (Nat.minFac n - 1) →
      (2 : ZMod (Nat.minFac n))^2 = 1 →
      Nat.minFac n ∣ 3 := by
  intro n hn _hdvd _hcop h2sq
  have h3 : (3 : ZMod (Nat.minFac n)) = 0 := by linear_combination h2sq
  exact (CharP.cast_eq_zero_iff (ZMod (Nat.minFac n)) (Nat.minFac n) 3).mp h3

end Problems.Minif2f.imo_1990_p3
