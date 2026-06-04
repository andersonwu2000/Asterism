import Mathlib
import Problems.Minif2f.mathd_algebra_185.Defs

namespace Problems.Minif2f.mathd_algebra_185

-- Direct proof: rewrite membership via h₀/h₁ to |x+4| < 9, then abs_lt + omega
-- shows s = Finset.Icc (-12) 4; cardinality follows by `decide`.
theorem s646 : ∀ (s : Finset ℤ) (f : ℤ → ℤ) (h₀ : ∀ x, f x = abs (x + 4))
    (h₁ : ∀ x, x ∈ s ↔ f x < 9), s.card = 17  := by
  intro s f h₀ h₁
  have h_eq : s = Finset.Icc (-12 : ℤ) 4 := by
    ext x
    rw [h₁ x, h₀ x, Finset.mem_Icc, abs_lt]
    omega
  rw [h_eq]
  decide

end Problems.Minif2f.mathd_algebra_185
