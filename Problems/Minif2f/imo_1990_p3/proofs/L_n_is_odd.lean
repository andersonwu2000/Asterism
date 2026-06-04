import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- n_is_odd: contrapositive via parity — if n is even then 2∣n²∣2^n+1,
-- but 2∣2^n forces 2^n+1 odd, contradiction by omega.
theorem n_is_odd : ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → Odd n := by
  intro n hn hdvd
  by_contra h
  rw [Nat.not_odd_iff_even] at h
  obtain ⟨k, hk⟩ := h
  have h2n2 : 2 ∣ n ^ 2 := ⟨2 * k ^ 2, by rw [hk]; ring⟩
  have h2pow : 2 ∣ 2 ^ n := dvd_pow (dvd_refl 2) (by omega)
  have h2sum : 2 ∣ 2 ^ n + 1 := h2n2.trans hdvd
  obtain ⟨a, ha⟩ := h2pow
  obtain ⟨b, hb⟩ := h2sum
  omega

end Problems.Minif2f.imo_1990_p3
