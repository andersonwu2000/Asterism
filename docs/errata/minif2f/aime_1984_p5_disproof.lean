/-
  Sandbox disproof of the minif2f-transcribed statement of `aime_1984_p5`.

  ## Background
  Statement (as imported):
    ∀ (a b : ℝ)
      (h₀ : Real.logb 8 a + Real.logb 4 (b ^ 2) = 5)
      (h₁ : Real.logb 8 b + Real.logb 4 (a ^ 2) = 7),
      a * b = 512

  ## Bug
  Mathlib's `Real.log` is defined as the even extension of natural log:
  `Real.log_neg_eq_log : Real.log (-x) = Real.log x`. Hence
  `Real.logb b (-x) = Real.logb b x` for any base. The hypotheses only
  pin |a|·|b| (via the logarithm equations) — they cannot distinguish
  signs of a and b. But the conclusion `a * b = 512` (positive) is
  sign-sensitive, so any sign-flipped solution disproves the theorem.

  ## Counterexample
  Take a = 64, b = -8:
    h₀: logb 8 64 + logb 4 ((-8)^2) = logb 8 64 + logb 4 64
        = 2 + 3 = 5 ✓
    h₁: logb 8 (-8) + logb 4 (64^2) = logb 8 8 + logb 4 4096
        = 1 + 6 = 7 ✓  (uses Real.log_neg_eq_log on logb 8 (-8))
    conclusion: a * b = 64 * (-8) = -512 ≠ 512 ✗

  The original AIME problem implicitly works in positive reals, so the
  intended unique solution is (a, b) = (64, 8). The Lean statement
  drops the positivity constraint, admitting all four sign variants:
  (±64, ±8) — only the two with matching signs satisfy a*b = +512.

  ## How to verify
    cd D:/Asterism
    lake env lean docs/errata/minif2f/aime_1984_p5_disproof.lean
  Expected: clean elaboration; axioms = [propext, Classical.choice, Quot.sound].
-/
import Mathlib

namespace Minif2fErrata.Aime1984P5

def stmt : Prop :=
  ∀ (a b : ℝ)
    (_ : Real.logb 8 a + Real.logb 4 (b ^ 2) = 5)
    (_ : Real.logb 8 b + Real.logb 4 (a ^ 2) = 7),
    a * b = 512

theorem disproof : ¬ stmt := by
  intro h
  -- Apply at (a, b) = (64, -8).
  -- We need: logb 8 64 + logb 4 64 = 5 and logb 8 8 + logb 4 4096 = 7
  -- (where logb 8 (-8) = logb 8 8 by log_neg_eq_log).
  have hlog2_pos : Real.log 2 > 0 :=
    Real.log_pos (by norm_num)
  have hlog2_ne : Real.log 2 ≠ 0 := ne_of_gt hlog2_pos
  have hlog8 : Real.log 8 = 3 * Real.log 2 := by
    have : (8 : ℝ) = 2 ^ (3 : ℕ) := by norm_num
    rw [this, Real.log_pow]; ring
  have hlog4 : Real.log 4 = 2 * Real.log 2 := by
    have : (4 : ℝ) = 2 ^ (2 : ℕ) := by norm_num
    rw [this, Real.log_pow]; ring
  have hlog64 : Real.log 64 = 6 * Real.log 2 := by
    have : (64 : ℝ) = 2 ^ (6 : ℕ) := by norm_num
    rw [this, Real.log_pow]; ring
  have hlog4096 : Real.log 4096 = 12 * Real.log 2 := by
    have : (4096 : ℝ) = 2 ^ (12 : ℕ) := by norm_num
    rw [this, Real.log_pow]; ring
  -- h₀ at (64, -8): logb 8 64 + logb 4 ((-8)^2) = 5
  --   (-8)^2 = 64, so logb 4 64 = log 64 / log 4 = 6·log 2 / (2·log 2) = 3
  --   logb 8 64 = log 64 / log 8 = 6·log 2 / (3·log 2) = 2
  have h0 : Real.logb 8 64 + Real.logb 4 ((-8 : ℝ) ^ 2) = 5 := by
    have hsq : ((-8 : ℝ)) ^ 2 = 64 := by norm_num
    rw [hsq]
    simp only [Real.logb, hlog8, hlog4, hlog64]
    field_simp
    ring
  -- h₁ at (64, -8): logb 8 (-8) + logb 4 (64^2) = 7
  --   logb 8 (-8): Real.log (-8) = Real.log 8 (by log_neg_eq_log), so
  --                logb 8 (-8) = log 8 / log 8 = 1.
  --   logb 4 (64^2) = log 4096 / log 4 = 12·log 2 / (2·log 2) = 6.
  have h1 : Real.logb 8 (-8 : ℝ) + Real.logb 4 ((64 : ℝ) ^ 2) = 7 := by
    have hsq : ((64 : ℝ)) ^ 2 = 4096 := by norm_num
    rw [hsq]
    simp only [Real.logb]
    have hneg : Real.log (-8 : ℝ) = Real.log 8 := by
      have : Real.log (-(8 : ℝ)) = Real.log 8 := Real.log_neg_eq_log 8
      simpa using this
    rw [hneg, hlog8, hlog4, hlog4096]
    field_simp
    ring
  -- Apply h to derive (64 : ℝ) * (-8) = 512, but it equals -512.
  have key := h 64 (-8) h0 h1
  norm_num at key

end Minif2fErrata.Aime1984P5

#print axioms Minif2fErrata.Aime1984P5.disproof
