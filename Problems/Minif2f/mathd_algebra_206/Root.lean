-- Eliminate f via h₀, reducing to pure algebra on a, b.
-- After `rw [h₀] at h₂ h₃`, h₂/h₃ become polynomial equations
-- (2a)^2 + a*(2a) + b = 0 and b^2 + a*b + b = 0. The single
-- sub-goal `algebraic_form` deduces a + b = -1 from these two
-- equations together with h₁ : 2*a ≠ b (pure ℝ-arithmetic case
-- split: h₃ factors as b*(a+b+1)=0; the b=0 branch contradicts h₁
-- via h₂; the a+b+1=0 branch closes the goal).
import Mathlib
import Problems.Minif2f.mathd_algebra_206.Defs
import Problems.Minif2f.mathd_algebra_206.proofs._strategy_s9301

namespace Problems.Minif2f.mathd_algebra_206

def main := @Problems.Minif2f.mathd_algebra_206.s9301

end Problems.Minif2f.mathd_algebra_206
