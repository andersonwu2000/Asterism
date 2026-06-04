import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs

namespace Problems.Minif2f.imo_1984_p2

-- seven_pow_dvd_of_pow_dvd_sq: Prime.dvd_of_dvd_pow applied three times,
-- peeling 7 ∣ q, 7 ∣ r, 7 ∣ s via subst + ring_nf + omega at each step.
theorem seven_pow_dvd_of_pow_dvd_sq : ∀ (q : ℤ),
    (7:ℤ) ^ 6 ∣ q ^ 2 → (7:ℤ) ^ 3 ∣ q := by
  intro q h
  have h7 : Prime (7 : ℤ) := by norm_num
  have hq1 : (7:ℤ) ∣ q := by
    apply h7.dvd_of_dvd_pow
    exact dvd_trans (by norm_num) h
  obtain ⟨r, hr⟩ := hq1
  subst hr
  have h4 : (7:ℤ)^4 ∣ r^2 := by
    have : (7:ℤ)^6 ∣ (7*r)^2 := h
    ring_nf at this ⊢
    omega
  have hr1 : (7:ℤ) ∣ r := by
    apply h7.dvd_of_dvd_pow
    exact dvd_trans (by norm_num) h4
  obtain ⟨s, hs⟩ := hr1
  subst hs
  have h2 : (7:ℤ)^2 ∣ s^2 := by
    have : (7:ℤ)^4 ∣ (7*s)^2 := h4
    ring_nf at this ⊢
    omega
  have hs1 : (7:ℤ) ∣ s := by
    apply h7.dvd_of_dvd_pow
    exact dvd_trans (by norm_num) h2
  obtain ⟨t, ht⟩ := hs1
  subst ht
  exact ⟨t, by ring⟩

end Problems.Minif2f.imo_1984_p2
