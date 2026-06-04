import Mathlib
import Problems.Minif2f.mathd_numbertheory_13.Defs
import Problems.Minif2f.mathd_numbertheory_13.proofs.L_u_eq_39
import Problems.Minif2f.mathd_numbertheory_13.proofs.L_v_eq_89

namespace Problems.Minif2f.mathd_numbertheory_13

-- Decompose into: (1) u = 39 (least positive n with 14n ≡ 46 mod 100), and
-- (2) v = 89 (next such n). Final combination is the arithmetic fact (39+89)/2 = 64.
theorem s695 : ∀ (u v : ℕ) (S : Set ℕ) (h₀ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ 14 * n % 100 = 46) (h₁ : IsLeast S u) (h₂ : IsLeast (S \ {u}) v), (u + v : ℚ) / 2 = 64  := by
  intro u v S h₀ h₁ h₂
  have hu : u = 39 := u_eq_39 u v S h₀ h₁ h₂
  have hv : v = 89 := v_eq_89 u v S h₀ h₁ h₂
  rw [hu, hv]
  norm_num
end Problems.Minif2f.mathd_numbertheory_13
