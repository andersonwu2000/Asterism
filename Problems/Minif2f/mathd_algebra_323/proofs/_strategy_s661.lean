import Mathlib
import Problems.Minif2f.mathd_algebra_323.Defs

namespace Problems.Minif2f.mathd_algebra_323

-- Direct proof: combine Equiv.right_inv (kills outer σ.1∘σ.2) with the cube identity h 3 : σ.1 3 = 27 - 8 = 19, then Equiv.left_inv yields σ.2 (σ.1 3) = 3.
theorem s661 : ∀ (σ : Equiv ℝ ℝ) (h : ∀ x, σ.1 x = x ^ 3 - 8), σ.2 (σ.1 (σ.2 19)) = 3  := by
  intro σ h
  have h19 : σ.1 3 = 19 := by rw [h 3]; norm_num
  rw [σ.right_inv, ← h19, σ.left_inv]

end Problems.Minif2f.mathd_algebra_323
