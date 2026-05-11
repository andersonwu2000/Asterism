/-
  Sandbox disproof of the minif2f-transcribed statement of
  `mathd_algebra_282`.

  ## Background
  Statement (as imported):
    ∀ (f : ℝ → ℝ)
      (h₀ : ∀ x : ℝ, ¬ Irrational x → f x = abs (Int.floor x))
      (h₁ : ∀ x, Irrational x → f x = (Int.ceil x) ^ 2),
      f (8 ^ (1 / 3)) + f (-Real.pi) + f (Real.sqrt 50) + f (9 / 2) = 79

  ## Bug
  The intended human reading is "8^(1/3) = 2" (the real cube root), giving
  f(2) + f(-π) + f(√50) + f(9/2) = 2 + 9 + 64 + 4 = 79.

  Lean elaborates `1 / 3` as ℕ-division (since both literals are ℕ in this
  position), so `1 / 3 = 0` and `(8 : ℝ) ^ (0 : ℕ) = 1`. Hence the first
  term is f(1) = |⌊1⌋| = 1, not f(2) = 2, and the sum is 78 instead of 79.

  Same `ℕ`-division trivialisation as `amc12a_2020_p13`.
-/
import Mathlib

namespace Minif2fErrata.MathdAlgebra282

def stmt : Prop :=
  ∀ (f : ℝ → ℝ)
    (_ : ∀ x : ℝ, ¬ Irrational x → f x = abs (Int.floor x))
    (_ : ∀ x, Irrational x → f x = (Int.ceil x) ^ 2),
    f (8 ^ (1 / 3)) + f (-Real.pi) + f (Real.sqrt 50) + f (9 / 2) = 79

private lemma sqrt_50_eq : Real.sqrt 50 = 5 * Real.sqrt 2 := by
  have h25 : Real.sqrt 25 = 5 := by
    rw [show (25 : ℝ) = 5 ^ 2 from by norm_num,
        Real.sqrt_sq (by norm_num : (0 : ℝ) ≤ 5)]
  calc Real.sqrt 50
      = Real.sqrt (25 * 2) := by norm_num
    _ = Real.sqrt 25 * Real.sqrt 2 :=
        Real.sqrt_mul (by norm_num : (0 : ℝ) ≤ 25) 2
    _ = 5 * Real.sqrt 2 := by rw [h25]

private lemma irr_sqrt_50 : Irrational (Real.sqrt 50) := by
  rw [sqrt_50_eq]
  intro ⟨q, hq⟩
  -- hq : (q : ℝ) = 5 * √2 ; show √2 is rational (= q/5) to contradict h2
  apply Nat.prime_two.irrational_sqrt
  refine ⟨q / 5, ?_⟩
  have hcast : ((q / 5 : ℚ) : ℝ) = (q : ℝ) / 5 := by push_cast; ring
  rw [hcast, hq]
  ring

private lemma not_irr_one : ¬ Irrational (1 : ℝ) := by
  have : (1 : ℝ) = ((1 : ℚ) : ℝ) := by norm_num
  rw [this]
  exact Rat.not_irrational 1

private lemma not_irr_half9 : ¬ Irrational ((9 : ℝ) / 2) := by
  have : ((9 : ℝ) / 2) = ((9 / 2 : ℚ) : ℝ) := by push_cast; ring
  rw [this]
  exact Rat.not_irrational (9 / 2)

private lemma irr_neg_pi : Irrational (-Real.pi) :=
  irrational_pi.neg

theorem disproof : ¬ stmt := by
  classical
  intro h
  -- Concrete witness: f x = (⌈x⌉)² if x is irrational, else |⌊x⌋|.
  let f : ℝ → ℝ := fun x =>
    if Irrational x then ((Int.ceil x : ℤ) : ℝ) ^ 2
    else |((Int.floor x : ℤ) : ℝ)|
  have h0 : ∀ x : ℝ, ¬ Irrational x → f x = abs (Int.floor x) := by
    intro x hx
    simp [f, hx, Int.cast_abs]
  have h1 : ∀ x, Irrational x → f x = (Int.ceil x) ^ 2 := by
    intro x hx
    simp [f, hx]
  -- (8 : ℝ) ^ (1 / 3) = 1 because 1/3 = 0 in ℕ
  have h_cube : (8 : ℝ) ^ (1 / 3 : ℕ) = 1 := by norm_num
  -- f at the four test points
  have hf1 : f 1 = 1 := by
    rw [h0 1 not_irr_one]
    simp [Int.floor_one]
  have hf_pi : f (-Real.pi) = ((Int.ceil (-Real.pi) : ℤ) : ℝ) ^ 2 := by
    have := h1 _ irr_neg_pi
    push_cast at this
    exact this
  have hf_sqrt50 : f (Real.sqrt 50)
      = ((Int.ceil (Real.sqrt 50) : ℤ) : ℝ) ^ 2 := by
    have := h1 _ irr_sqrt_50
    push_cast at this
    exact this
  have hf_92 : f ((9 : ℝ) / 2)
      = |((Int.floor ((9 : ℝ) / 2) : ℤ) : ℝ)| := by
    have := h0 _ not_irr_half9
    push_cast at this
    exact this
  -- Concrete integer values: ⌈-π⌉ = -3, ⌈√50⌉ = 8, ⌊9/2⌋ = 4
  have h_ceil_pi : Int.ceil (-Real.pi) = -3 := by
    apply Int.ceil_eq_iff.mpr
    refine ⟨?_, ?_⟩
    · -- (-3 : ℤ) - 1 = -4, need -4 < -π
      have h_pi_lt_4 : Real.pi < 4 := Real.pi_lt_four
      push_cast
      linarith
    · -- need -π ≤ -3
      have h_pi_ge_3 : (3 : ℝ) ≤ Real.pi := Real.pi_gt_three.le
      push_cast
      linarith
  have h_ceil_sqrt50 : Int.ceil (Real.sqrt 50) = 8 := by
    apply Int.ceil_eq_iff.mpr
    refine ⟨?_, ?_⟩
    · -- need 7 < √50
      have h49 : Real.sqrt 49 = 7 := by
        rw [show (49 : ℝ) = 7 ^ 2 from by norm_num,
            Real.sqrt_sq (by norm_num : (0 : ℝ) ≤ 7)]
      have h_lt : Real.sqrt 49 < Real.sqrt 50 :=
        Real.sqrt_lt_sqrt (by norm_num) (by norm_num)
      push_cast; linarith [h49 ▸ h_lt]
    · -- need √50 ≤ 8
      have h64 : Real.sqrt 64 = 8 := by
        rw [show (64 : ℝ) = 8 ^ 2 from by norm_num,
            Real.sqrt_sq (by norm_num : (0 : ℝ) ≤ 8)]
      have h_le : Real.sqrt 50 ≤ Real.sqrt 64 :=
        Real.sqrt_le_sqrt (by norm_num)
      push_cast; linarith [h64 ▸ h_le]
  have h_floor_92 : Int.floor ((9 : ℝ) / 2) = 4 := by
    apply Int.floor_eq_iff.mpr
    refine ⟨?_, ?_⟩ <;> push_cast <;> norm_num
  -- Apply hypothesis at f
  have key := h f h0 h1
  rw [h_cube, hf1, hf_pi, hf_sqrt50, hf_92,
      h_ceil_pi, h_ceil_sqrt50, h_floor_92] at key
  -- key : (1 : ℝ) + (-3)^2 + 8^2 + |4| = 79 → 1 + 9 + 64 + 4 = 78 ≠ 79
  norm_num at key

end Minif2fErrata.MathdAlgebra282

#print axioms Minif2fErrata.MathdAlgebra282.disproof
