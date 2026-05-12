/-
  Sandbox disproof of the minif2f-transcribed statement of `imo_1967_p3`.

  ## Background
  Statement (as imported):
    ∀ (k m n : ℕ) (c : ℕ → ℕ)
      (h₀ : 0 < k ∧ 0 < m ∧ 0 < n)
      (h₁ : ∀ s, c s = s * (s + 1))
      (h₂ : Nat.Prime (k + m + 1))
      (h₃ : n + 1 < k + m + 1),
      (∏ i ∈ Finset.Icc 1 n, c i) ∣ ∏ i ∈ Finset.Icc 1 n, c (m + i) - c k

  ## Bug — operator precedence
  In Mathlib's `BigOperators` notation, `∏ i ∈ s, body` is declared with
  body precedence 67. Natural subtraction is at precedence 65, lower. So
  the RHS parses as

      (∏ i ∈ Finset.Icc 1 n, c (m + i)) - c k         -- a product, then subtract c k

  NOT as the intended IMO 1967 P3 statement

      ∏ i ∈ Finset.Icc 1 n, (c (m + i) - c k)         -- product of differences

  The original problem multiplies differences. The Lean version computes
  a single subtraction of `c k` from a plain product — a fundamentally
  different quantity.

  ## Counterexample
  Take k = 5, m = 1, n = 2, c(s) = s*(s+1):
    h₀: 0 < 5 ∧ 0 < 1 ∧ 0 < 2 ✓
    h₁: by definition ✓
    h₂: k + m + 1 = 7, prime ✓
    h₃: n + 1 = 3 < 7 ✓
    LHS = c(1) · c(2)         = 2 · 6 = 12
    ∏ i ∈ Icc 1 2, c(1 + i) = c(2) · c(3) = 6 · 12 = 72
    c(5)                     = 30
    RHS = 72 - 30            = 42  (Nat subtraction; 72 ≥ 30, no truncation)
    12 ∣ 42 is false (42 = 12·3 + 6).

  ## How to verify
    cd D:/Asterism
    lake env lean docs/errata/minif2f/imo_1967_p3_disproof.lean
  Expected: clean elaboration; axioms = [propext, Classical.choice, Quot.sound].
-/
import Mathlib

namespace Minif2fErrata.Imo1967P3

def stmt : Prop :=
  ∀ (k m n : ℕ) (c : ℕ → ℕ)
    (_ : 0 < k ∧ 0 < m ∧ 0 < n)
    (_ : ∀ s, c s = s * (s + 1))
    (_ : Nat.Prime (k + m + 1))
    (_ : n + 1 < k + m + 1),
    (∏ i ∈ Finset.Icc 1 n, c i) ∣ ∏ i ∈ Finset.Icc 1 n, c (m + i) - c k

theorem disproof : ¬ stmt := by
  intro h
  -- Apply at k = 5, m = 1, n = 2, c s = s * (s + 1).
  have h0 : 0 < (5 : ℕ) ∧ 0 < (1 : ℕ) ∧ 0 < (2 : ℕ) := by decide
  have h1 : ∀ s : ℕ, (fun s => s * (s + 1)) s = s * (s + 1) := fun _ => rfl
  have h2 : Nat.Prime (5 + 1 + 1) := by decide
  have h3 : 2 + 1 < 5 + 1 + 1 := by decide
  have key := h 5 1 2 (fun s => s * (s + 1)) h0 h1 h2 h3
  -- key : (∏ i ∈ Icc 1 2, c i) ∣ (∏ i ∈ Icc 1 2, c (1 + i)) - c 5
  --     = 12 ∣ 42
  -- But 12 ∤ 42, so contradiction.
  exact absurd key (by decide)

end Minif2fErrata.Imo1967P3

#print axioms Minif2fErrata.Imo1967P3.disproof
