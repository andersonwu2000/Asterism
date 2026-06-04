import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- odd_of_sq_dvd_pow_succ: if m² ∣ 2^m+1 and m ≥ 2, then m is odd;
-- parity argument: even m gives 2 ∣ m² ∣ 2^m+1, but 2^m+1 is odd.
theorem odd_of_sq_dvd_pow_succ :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → Odd m := by
  intro m hm hdvd
  by_contra h
  rw [Nat.not_odd_iff_even] at h
  have h2m : 2 ∣ m := h.two_dvd
  have h2m2 : 2 ∣ m ^ 2 := dvd_pow h2m (by norm_num)
  have h2sum : 2 ∣ 2 ^ m + 1 := h2m2.trans hdvd
  have h2pow : 2 ∣ 2 ^ m := dvd_pow_self 2 (by omega)
  obtain ⟨a, ha⟩ := h2sum
  obtain ⟨b, hb⟩ := h2pow
  omega

end Problems.Minif2f.imo_1990_p3
