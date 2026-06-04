import Mathlib
namespace Problems.Minif2f.amc12a_2019_p21

-- sum_pow_sq_odd: z^(8n+1)=z via hz8; expand sum_insert, map each odd k^2≡1(mod8) to hpow
theorem sum_pow_sq_odd : ∀ (z : ℂ) (_h₀ : z = (1 + Complex.I) / Real.sqrt 2)
    (_hz4 : z ^ 4 = -1) (_hzne : z ≠ 0) (_hz8 : z ^ 8 = 1),
    (∑ k ∈ ({1,3,5,7,9,11} : Finset ℕ), z ^ k ^ 2) = 6 * z := by
  intro z _h₀ _hz4 _hzne hz8
  have hpow : ∀ n : ℕ, z ^ (8 * n + 1) = z := by
    intro n; rw [pow_add, pow_mul, hz8, one_pow, one_mul, pow_one]
  simp only [Finset.sum_insert (show (1:ℕ) ∉ ({3,5,7,9,11} : Finset ℕ) by norm_num),
             Finset.sum_insert (show (3:ℕ) ∉ ({5,7,9,11} : Finset ℕ) by norm_num),
             Finset.sum_insert (show (5:ℕ) ∉ ({7,9,11} : Finset ℕ) by norm_num),
             Finset.sum_insert (show (7:ℕ) ∉ ({9,11} : Finset ℕ) by norm_num),
             Finset.sum_insert (show (9:ℕ) ∉ ({11} : Finset ℕ) by norm_num),
             Finset.sum_singleton]
  rw [show (1:ℕ)^2 = 8*0+1 from rfl, hpow,
      show (3:ℕ)^2 = 8*1+1 from rfl, hpow,
      show (5:ℕ)^2 = 8*3+1 from rfl, hpow,
      show (7:ℕ)^2 = 8*6+1 from rfl, hpow,
      show (9:ℕ)^2 = 8*10+1 from rfl, hpow,
      show (11:ℕ)^2 = 8*15+1 from rfl, hpow]
  ring

end Problems.Minif2f.amc12a_2019_p21
