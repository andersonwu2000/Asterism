import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_gcd_two_m_p_sub_one_dvd_two

namespace Problems.Minif2f.imo_1990_p3

-- Split gcd = 2 into upper bound (gcd ∣ 2) and lower bound (2 ∣ gcd) via dvd_antisymm.
-- Lower bound is trivial: 2 ∣ 2m, and p odd (p prime ≥ 5) gives 2 ∣ p-1.
-- Upper bound carries the entire argument and is delegated to the sub-goal.
theorem s9836 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ m → Nat.gcd (2 * m) (p - 1) = 2  := by
  intro m hm hdvd h3 h9 h7 p hp h5 hpm
  have h_le := gcd_two_m_p_sub_one_dvd_two m hm hdvd h3 h9 h7 p hp h5 hpm
  have h_ge : 2 ∣ Nat.gcd (2 * m) (p - 1) := by
    refine Nat.dvd_gcd ?_ ?_
    · exact ⟨m, rfl⟩
    · have hp_odd : Odd p := hp.odd_of_ne_two (by omega)
      obtain ⟨k, hk⟩ := hp_odd
      exact ⟨k, by omega⟩
  exact Nat.dvd_antisymm h_le h_ge

end Problems.Minif2f.imo_1990_p3
