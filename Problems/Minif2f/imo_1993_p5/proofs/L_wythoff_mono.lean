import Mathlib
namespace Problems.Minif2f.imo_1993_p5

-- wythoff_mono: strict monotonicity of ⌊(n+1)φ⌋−1 via φ>1 giving floor gap ≥ 1
-- φ=(1+√5)/2>1 implies (n+2)φ>(n+1)φ+1, so ⌊(n+2)φ⌋≥⌊(n+1)φ⌋+1; omega closes ℕ.sub.
theorem wythoff_mono : ∀ n : ℕ,
    (fun m : ℕ => (⌊((m : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋).toNat - 1) n
      < (fun m : ℕ => (⌊((m : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋).toNat - 1) (n + 1) := by
  intro n
  simp only
  push_cast
  have key : ((n : ℝ) + 1 + 1) = ((n : ℝ) + 2) := by ring
  rw [key]
  set φ := (1 + Real.sqrt 5) / 2 with hφ_def
  have hphi : (1 : ℝ) < φ := by
    have h5 : (1 : ℝ) < Real.sqrt 5 := by
      linarith [Real.sqrt_lt_sqrt (by norm_num : (0 : ℝ) ≤ 1) (by norm_num : (1 : ℝ) < 5),
                Real.sqrt_one]
    simp only [hφ_def]; linarith
  have hfloor_ineq : ⌊((n : ℝ) + 1) * φ⌋ + 1 ≤ ⌊((n : ℝ) + 2) * φ⌋ := by
    rw [Int.le_floor]; push_cast
    have hle := Int.floor_le (((n : ℝ) + 1) * φ)
    linarith [show ((n : ℝ) + 2) * φ = ((n : ℝ) + 1) * φ + φ from by ring]
  have hfloor_pos : 1 ≤ ⌊((n : ℝ) + 1) * φ⌋ := by
    rw [Int.le_floor]; push_cast
    have : (0 : ℝ) ≤ (n : ℝ) := Nat.cast_nonneg n
    nlinarith
  have ha_nn : 0 ≤ ⌊((n : ℝ) + 1) * φ⌋ := by linarith
  have hb_nn : 0 ≤ ⌊((n : ℝ) + 2) * φ⌋ := by linarith
  have ha_eq := Int.toNat_of_nonneg ha_nn
  have hb_eq := Int.toNat_of_nonneg hb_nn
  omega

end Problems.Minif2f.imo_1993_p5
