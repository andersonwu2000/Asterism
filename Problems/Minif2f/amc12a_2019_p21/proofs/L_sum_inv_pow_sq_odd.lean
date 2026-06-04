import Mathlib
namespace Problems.Minif2f.amc12a_2019_p21

-- sum_inv_pow_sq_odd: z^8=1 and k^2≡1 (mod 8) for odd k, so 1/z^(k^2)=1/z; 6 terms give 6/z
theorem sum_inv_pow_sq_odd : ∀ (z : ℂ) (_h₀ : z = (1 + Complex.I) / Real.sqrt 2)
    (_hz4 : z ^ 4 = -1) (_hzne : z ≠ 0),
    (∑ k ∈ ({1,3,5,7,9,11} : Finset ℕ), 1 / z ^ k ^ 2) = 6 / z := by
  intro z _h₀ hz4 hzne
  have hz8 : z ^ 8 = 1 := by
    calc z ^ 8 = (z ^ 4) ^ 2 := by ring
      _ = (-1 : ℂ) ^ 2 := by rw [hz4]
      _ = 1 := by norm_num
  have hpow : ∀ n : ℕ, z ^ (8 * n + 1) = z := by
    intro n
    have : z ^ (8 * n + 1) = (z ^ 8) ^ n * z := by ring
    rw [this, hz8, one_pow, one_mul]
  have hk1 : z ^ ((1 : ℕ) ^ 2) = z := by norm_num
  have hk3 : z ^ ((3 : ℕ) ^ 2) = z := by norm_num; exact hpow 1
  have hk5 : z ^ ((5 : ℕ) ^ 2) = z := by norm_num; exact hpow 3
  have hk7 : z ^ ((7 : ℕ) ^ 2) = z := by norm_num; exact hpow 6
  have hk9 : z ^ ((9 : ℕ) ^ 2) = z := by norm_num; exact hpow 10
  have hk11 : z ^ ((11 : ℕ) ^ 2) = z := by norm_num; exact hpow 15
  simp only [Finset.sum_insert (by decide : (1 : ℕ) ∉ ({3,5,7,9,11} : Finset ℕ)),
             Finset.sum_insert (by decide : (3 : ℕ) ∉ ({5,7,9,11} : Finset ℕ)),
             Finset.sum_insert (by decide : (5 : ℕ) ∉ ({7,9,11} : Finset ℕ)),
             Finset.sum_insert (by decide : (7 : ℕ) ∉ ({9,11} : Finset ℕ)),
             Finset.sum_insert (by decide : (9 : ℕ) ∉ ({11} : Finset ℕ)),
             Finset.sum_singleton]
  rw [show (1 : ℕ) ^ 2 = 1 from by norm_num, show (3 : ℕ) ^ 2 = 9 from by norm_num,
      show (5 : ℕ) ^ 2 = 25 from by norm_num, show (7 : ℕ) ^ 2 = 49 from by norm_num,
      show (9 : ℕ) ^ 2 = 81 from by norm_num, show (11 : ℕ) ^ 2 = 121 from by norm_num]
  have h1 : z ^ 1 = z := pow_one z
  have h9 : z ^ 9 = z := hpow 1
  have h25 : z ^ 25 = z := hpow 3
  have h49 : z ^ 49 = z := hpow 6
  have h81 : z ^ 81 = z := hpow 10
  have h121 : z ^ 121 = z := hpow 15
  rw [h1, h9, h25, h49, h81, h121]
  field_simp
  ring

end Problems.Minif2f.amc12a_2019_p21
