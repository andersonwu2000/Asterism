/-
  Sandbox disproof of the minif2f-transcribed statement of
  `mathd_numbertheory_126`.

  ## Background
  Statement (as imported):
    ∀ (x a : ℕ) (h₀ : 0 < x ∧ 0 < a)
      (h₁ : Nat.gcd a 40 = x + 3)
      (h₂ : Nat.lcm a 40 = x * (x + 3))
      (h₃ : ∀ b : ℕ, 0 < b → Nat.gcd b 40 = x + 3 ∧ Nat.lcm b 40 = x * (x + 3) → a ≤ b),
      a = 8

  ## Bug
  h₃ asserts a is the minimum among b satisfying the gcd/lcm conditions
  *for the same fixed x*. The original AMC problem requires minimality
  over ALL pairs (x', b) satisfying the constraints. Two valid (x, a)
  pairs exist: (x=5, a=8) and (x=37, a=1480). h₃ rules out the second
  branch within x=37 only.

  ## Counterexample
  Take x = 37, a = 1480.
    h₁: gcd 1480 40 = 40 = 37 + 3.
    h₂: lcm 1480 40 = 1480 = 37 * 40 = 37 * (37 + 3).
    h₃: For b > 0 with gcd b 40 = 40 ∧ lcm b 40 = 1480: gcd b 40 = 40
        means 40 ∣ b, then lcm b 40 = b · 40 / 40 = b, so b = 1480.
        Hence a = 1480 ≤ b = 1480. ✓
  Yet a = 1480, not 8.

  ## How to verify
    cd D:/Asterism
    lake env lean .asterism/sandbox/mathd_numbertheory_126_disproof.lean
  Expected: clean elaboration; axioms = [propext, Classical.choice, Quot.sound].
-/
import Mathlib

namespace Minif2fErrata.MathdNumbertheory126

def stmt : Prop :=
  ∀ (x a : ℕ) (_ : 0 < x ∧ 0 < a)
    (_ : Nat.gcd a 40 = x + 3)
    (_ : Nat.lcm a 40 = x * (x + 3))
    (_ : ∀ b : ℕ, 0 < b →
           Nat.gcd b 40 = x + 3 ∧ Nat.lcm b 40 = x * (x + 3) → a ≤ b),
    a = 8

theorem disproof : ¬ stmt := by
  intro h
  -- Plug in x = 37, a = 1480 and watch a = 8 fail.
  have h0 : (0 : ℕ) < 37 ∧ (0 : ℕ) < 1480 := by decide
  have h1 : Nat.gcd 1480 40 = 37 + 3 := by decide
  have h2 : Nat.lcm 1480 40 = 37 * (37 + 3) := by decide
  have h3 : ∀ b : ℕ, 0 < b →
              Nat.gcd b 40 = 37 + 3 ∧ Nat.lcm b 40 = 37 * (37 + 3) →
              1480 ≤ b := by
    intro b _ ⟨hg, hl⟩
    -- hg : gcd b 40 = 40, hl : lcm b 40 = 1480.
    -- Identity gcd * lcm = a * b: 40 * 1480 = b * 40, so b = 1480.
    have key : Nat.gcd b 40 * Nat.lcm b 40 = b * 40 := Nat.gcd_mul_lcm b 40
    rw [hg, hl] at key
    -- key : 40 * 1480 = b * 40
    omega
  -- Apply the hypothesis at x=37, a=1480.
  have step := h 37 1480 h0 h1 h2 h3
  -- step : 1480 = 8 — false.
  exact absurd step (by decide)

end Minif2fErrata.MathdNumbertheory126

#print axioms Minif2fErrata.MathdNumbertheory126.disproof
