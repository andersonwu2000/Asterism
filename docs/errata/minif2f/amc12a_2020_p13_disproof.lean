/-
  Sandbox disproof of the minif2f-transcribed statement of
  `amc12a_2020_p13`.

  ## Background
  Statement (as imported):
    ∀ (a b c : ℕ) (n : NNReal)
      (h₀ : n ≠ 1) (h₁ : 1 < a ∧ 1 < b ∧ 1 < c)
      (h₂ : (n * (n * n ^ (1 / c)) ^ (1 / b)) ^ (1 / a) = (n ^ 25) ^ (1 / 36)),
      b = 3

  ## Bug
  Since `a b c : ℕ`, all of `1 / a`, `1 / b`, `1 / c`, `1 / 36` are
  evaluated as natural-number division. For any natural `k ≥ 2`,
  `1 / k = 0`. The exponentiations `n ^ (1/k)` therefore reduce to
  `n ^ 0 = 1` (monoid power on NNReal), collapsing both sides of `h₂`
  to `1 = 1` regardless of n. The conclusion `b = 3` is then completely
  unconstrained.

  The original AMC 2020 12A #13 problem treats `1/a`, `1/b`, `1/c` as
  real exponents (radical-tower interpretation). The Lean transcription
  uses ℕ-division, which trivializes the equation.

  ## Counterexample
  Take a = b = c = 2, n = 2:
    h₀: (2 : NNReal) ≠ 1 ✓
    h₁: 1 < 2 ∧ 1 < 2 ∧ 1 < 2 ✓
    h₂: ((2 * (2 * 2^(1/2))^(1/2))^(1/2)) = (2^25)^(1/36)
        With 1/2 = 0 (ℕ): LHS = (2 * (2 * 1)^0)^0 = 1; RHS = (2^25)^0 = 1 ✓
    conclusion: b = 3 fails since b = 2.

  ## How to verify
    cd D:/Asterism
    lake env lean docs/errata/minif2f/amc12a_2020_p13_disproof.lean
  Expected: clean elaboration; axioms = [propext, Classical.choice, Quot.sound].
-/
import Mathlib

namespace Minif2fErrata.Amc12a2020P13

def stmt : Prop :=
  ∀ (a b c : ℕ) (n : NNReal)
    (_ : n ≠ 1) (_ : 1 < a ∧ 1 < b ∧ 1 < c)
    (_ : (n * (n * n ^ (1 / c)) ^ (1 / b)) ^ (1 / a) = (n ^ 25) ^ (1 / 36)),
    b = 3

theorem disproof : ¬ stmt := by
  intro h
  -- Apply at a = b = c = 2, n = 2.
  have h0 : ((2 : NNReal)) ≠ 1 := by
    intro hc
    have := congrArg ((↑) : NNReal → ℝ) hc
    simp at this
  have h1 : 1 < (2 : ℕ) ∧ 1 < (2 : ℕ) ∧ 1 < (2 : ℕ) := by decide
  -- For h₂, all the `1 / 2` and `1 / 36` are ℕ-division = 0, so n ^ 0 = 1.
  have h2 : ((2 : NNReal) * ((2 : NNReal) * (2 : NNReal) ^ (1 / 2))
            ^ (1 / 2)) ^ (1 / 2) = ((2 : NNReal) ^ 25) ^ (1 / 36) := by
    -- 1/2 = 0 in ℕ, 1/36 = 0 in ℕ. Both sides reduce to 1.
    show ((2 : NNReal) * ((2 : NNReal) * (2 : NNReal) ^ (0 : ℕ))
            ^ (0 : ℕ)) ^ (0 : ℕ) = ((2 : NNReal) ^ 25) ^ (0 : ℕ)
    simp
  -- Apply the hypothesis at b = 2; conclusion claims b = 3.
  have key := h 2 2 2 2 h0 h1 h2
  -- key : (2 : ℕ) = 3
  exact absurd key (by decide)

end Minif2fErrata.Amc12a2020P13

#print axioms Minif2fErrata.Amc12a2020P13.disproof
