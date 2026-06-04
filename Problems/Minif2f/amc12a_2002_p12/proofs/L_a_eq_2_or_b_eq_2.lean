import Mathlib
import Problems.Minif2f.amc12a_2002_p12.Defs

namespace Problems.Minif2f.amc12a_2002_p12

-- a_eq_2_or_b_eq_2: parity argument — odd sum 63 forces one prime to be 2
-- Both primes odd ⇒ sum even, contradicting 63; so one must equal 2.
theorem a_eq_2_or_b_eq_2 : ∀ (f : ℝ → ℝ) (k : ℝ) (a b : ℕ),
    (∀ x, f x = x ^ 2 - 63 * x + k) →
    (f a = 0 ∧ f b = 0) →
    a ≠ b →
    (Nat.Prime a ∧ Nat.Prime b) →
    a + b = 63 →
    a = 2 ∨ b = 2 := by
  intro f k a b hf hfab hab hprime hsum
  obtain ⟨hpa, hpb⟩ := hprime
  by_contra h
  push Not at h
  obtain ⟨ha2, hb2⟩ := h
  have ha_odd : a % 2 = 1 := by
    have h2 : ¬ 2 ∣ a := fun hdvd => by
      rcases hpa.eq_one_or_self_of_dvd 2 hdvd with h | h
      · norm_num at h
      · exact ha2 h.symm
    omega
  have hb_odd : b % 2 = 1 := by
    have h2 : ¬ 2 ∣ b := fun hdvd => by
      rcases hpb.eq_one_or_self_of_dvd 2 hdvd with h | h
      · norm_num at h
      · exact hb2 h.symm
    omega
  omega

end Problems.Minif2f.amc12a_2002_p12
