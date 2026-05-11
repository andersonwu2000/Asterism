import Mathlib

set_option maxHeartbeats 0

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.amc12a_2009_p25

/-- Helper angle sequence for the tangent-addition approach to
    `amc12a_2009_p25`. Defined by θ 1 = π/4 (so tan = 1 = a 1),
    θ 2 = π/6 (so tan = 1/√3 = a 2), θ (n+2) = θ n + θ (n+1) for n ≥ 1.
    Under this, the problem's `a` satisfies `a n = tan (θ n)`, and the
    tangent-addition identity matches the given recurrence.

    The proof reduces `abs (a 2009) = 0` to showing `θ 2009 ≡ 0 (mod π)`
    (so tan vanishes). This holds because the sequence `12 · θ n / π` is
    a Fibonacci-style recurrence over ℤ with starting pair (3, 2)
    (since π/4 = 3·(π/12), π/6 = 2·(π/12)), and 12·θ 17 / π ≡ 0 (mod 12)
    placing θ 17 at an integer multiple of π. The Fibonacci pair has
    period 24 modulo 12, and 2009 ≡ 17 (mod 24), so θ 2009 is also an
    integer multiple of π.

    Index 0 is set to 0 (arbitrary; never referenced — the problem's
    `a` and the recurrence both start at n ≥ 1).
-/
noncomputable def θ : ℕ → ℝ
  | 0     => 0
  | 1     => Real.pi / 4
  | 2     => Real.pi / 6
  | n + 3 => θ (n + 1) + θ (n + 2)

end Problems.Minif2f.amc12a_2009_p25
