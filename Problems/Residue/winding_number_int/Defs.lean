import Mathlib

namespace Complex

open Classical in
/--
Winding number of a C¹ closed path `γ : ℝ → ℂ` around a point `a ∈ ℂ`.

Defined classically: if there exists an integer `k : ℤ` such that
`∫ t in 0..1, deriv γ t / (γ t - a) = 2πi · k`, return that `k`;
otherwise return `0`.

For C¹ closed paths whose image avoids `a`, such a `k` always exists
(integrality theorem — the content of `Residue.winding_number_int`).
Outside that hypothesis class the default `0` makes the function total
without committing to a value.
-/
noncomputable def windingNumber (γ : ℝ → ℂ) (a : ℂ) : ℤ :=
  if h : ∃ k : ℤ,
        (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 2 * Real.pi * Complex.I * k
    then Classical.choose h
    else 0

end Complex
