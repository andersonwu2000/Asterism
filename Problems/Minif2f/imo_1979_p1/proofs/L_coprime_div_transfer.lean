import Mathlib
namespace Problems.Minif2f.imo_1979_p1

-- coprime_div_transfer: cross-multiply the real equality to ℕ, then transfer 1979∣a via Nat.Coprime.dvd_of_dvd_mul_right
theorem coprime_div_transfer :
    ∀ (p' q' a b : ℕ), 0 < q' → 0 < b → Nat.Coprime b 1979 → 1979 ∣ a →
      (a : ℝ) / (b : ℝ) = (p' : ℝ) / (q' : ℝ) → 1979 ∣ p' := by
  intro p' q' a b hq' hb hcop hdvd heq
  have hb' : (b : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr hb.ne'
  have hq'' : (q' : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr hq'.ne'
  have heq' : (a : ℝ) * q' = p' * b := by
    rwa [div_eq_div_iff hb' hq''] at heq
  have heq_nat : a * q' = p' * b := by exact_mod_cast heq'
  have hdvd1 : 1979 ∣ a * q' := hdvd.mul_right q'
  rw [heq_nat] at hdvd1
  exact hcop.symm.dvd_of_dvd_mul_right hdvd1

end Problems.Minif2f.imo_1979_p1
