import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11436

namespace Problems.Geometry.banach_tarski

-- Power law for the z-rotation block by induction on `n`, reusing the proved
-- multiplication law `s11436 : M(α)·M(β) = M(α+β)`.
-- Base `n=0`: `M^0 = 1 = M(0)`. Step: `M^(k+1) = M^k·M = M(kθ)·M(θ) = M((k+1)θ)`.
theorem s11445 (θ : ℝ) (n : ℕ) :
    (!![Real.cos θ, -Real.sin θ, 0;
        Real.sin θ,  Real.cos θ, 0;
        0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) ^ n
      = !![Real.cos ((n : ℝ) * θ), -Real.sin ((n : ℝ) * θ), 0;
           Real.sin ((n : ℝ) * θ),  Real.cos ((n : ℝ) * θ), 0;
           0,                       0,                      1]  := by
  induction n with
  | zero =>
    simp only [pow_zero, Nat.cast_zero, zero_mul, Real.cos_zero, Real.sin_zero, neg_zero]
    ext i j
    fin_cases i <;> fin_cases j <;> simp
  | succ k ih =>
    rw [pow_succ, ih, s11436]
    have : ((k + 1 : ℕ) : ℝ) * θ = (k : ℝ) * θ + θ := by push_cast; ring
    rw [this]

end Problems.Geometry.banach_tarski
