import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_412

-- xp1_sq_mod: Int.emod + obtain substitution — reduces x to 19k+4, then norm_num closes 5^2%19=6
theorem xp1_sq_mod : ∀ (x : ℤ), x % 19 = 4 → (x + 1) ^ 2 % 19 = 6 := by
  intro x hx
  obtain ⟨k, rfl⟩ : ∃ k, x = 19 * k + 4 := ⟨x / 19, by omega⟩
  norm_num [Int.add_mul_emod_self_left, pow_succ, Int.mul_emod, Int.add_emod]

end Problems.Minif2f.mathd_numbertheory_412
