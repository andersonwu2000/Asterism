import Mathlib
import Problems.Minif2f.mathd_algebra_69.Defs

namespace Problems.Minif2f.mathd_algebra_69

-- Direct: seats ≥ 3 (else (rows+5)*0 ≠ 450), then linear 5·seats = 3·rows + 15 from
-- expanding h₁ via h₀; substitute into h₀ → quadratic closed by nlinarith with (rows-25)².
theorem s690 : ∀ (rows seats : ℕ) (h₀ : rows * seats = 450) (h₁ : (rows + 5) * (seats - 3) = 450), rows = 25  := by
  intro rows seats h₀ h₁
  have hs : seats ≥ 3 := by
    by_contra h
    push_neg at h
    interval_cases seats <;> omega
  have hlin : 5 * seats = 3 * rows + 15 := by
    have := h₁
    rw [Nat.mul_sub] at this
    have hrs : (rows + 5) * seats = rows * seats + 5 * seats := by ring
    omega
  nlinarith [h₀, hlin, sq_nonneg (rows - 25 : ℤ), sq_nonneg (rows + 30 : ℤ)]

end Problems.Minif2f.mathd_algebra_69
