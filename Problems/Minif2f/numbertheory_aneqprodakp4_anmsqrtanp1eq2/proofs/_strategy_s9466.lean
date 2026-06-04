import Mathlib
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.Defs

namespace Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2

-- Direct proof: from h₁ m we get ∏_{k<m+1} a k = a (m+1) - 4; substitute into
-- h₁ (m+1) and ring-close (a(m+1)-4)*a(m+1) + 4 = (a(m+1)-2)^2.
theorem s9466 : ∀ (a : ℕ → ℝ) (_h₀ : a 0 = 1)
    (h₁ : ∀ n, a (n + 1) = (∏ k ∈ Finset.range (n + 1), a k) + 4)
    (n : ℕ) (_hn : n ≥ 1), a (n + 1) = (a n - 2) ^ 2  := by
  intro a _h₀ h₁ n hn
  obtain ⟨m, rfl⟩ := Nat.exists_eq_succ_of_ne_zero (Nat.one_le_iff_ne_zero.mp hn)
  have h_an := h₁ m
  have h_an1 := h₁ (m + 1)
  rw [Finset.prod_range_succ] at h_an1
  have key : (∏ k ∈ Finset.range (m+1), a k) = a (m+1) - 4 := by linarith
  rw [key] at h_an1
  rw [h_an1]
  ring

end Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2
