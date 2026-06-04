import Mathlib
import Problems.Minif2f.imo_2006_p3.Defs

namespace Problems.Minif2f.imo_2006_p3

-- cubed_linear_am_gm: AM-GM bound 256u³v ≤ 27(u+v)⁴ via SOS identity
-- RHS−LHS = (u−3v)²·(27u²+14uv+3v²); the second factor is PSD (disc < 0).
-- entry_kind: Builder
theorem cubed_linear_am_gm : ∀ (u v : ℝ),
    256 * u^3 * v ≤ 27 * (u + v)^4 := by
  intro u v
  have h1 : 0 ≤ (u - 3*v)^2 := sq_nonneg _
  have h2 : 0 ≤ 27*u^2 + 14*u*v + 3*v^2 := by
    nlinarith [sq_nonneg (3*u + v), sq_nonneg u, sq_nonneg v]
  nlinarith [mul_nonneg h1 h2]

end Problems.Minif2f.imo_2006_p3
