import Mathlib
namespace Problems.Minif2f.aime_1991_p6

-- sum_floor_le_545_of_r_lt: bound floor sum ≤ 545 when r < 7.43 via per-term floor bounds
-- Split Icc 19 91 into [19,57] (39 terms, each floor ≤ 7) and [58,91] (34 terms, each floor ≤ 8).
-- 39*7 + 34*8 = 273 + 272 = 545. Each floor bound follows from r+k/100 < n+1 via Int.floor_lt.
theorem sum_floor_le_545_of_r_lt :
    ∀ (r : ℝ), r < (743 : ℝ)/100 →
      (∑ k ∈ Finset.Icc (19 : ℕ) 91, Int.floor (r + k / 100)) ≤ 545 := by
  intro r hr
  rw [show Finset.Icc (19 : ℕ) 91 = Finset.Icc 19 57 ∪ Finset.Icc 58 91 from by
    ext x; simp only [Finset.mem_Icc, Finset.mem_union]; omega,
    Finset.sum_union (by simp only [Finset.disjoint_left, Finset.mem_Icc]; omega)]
  have h1 : ∑ k ∈ Finset.Icc (19 : ℕ) 57, ⌊r + k / 100⌋ ≤ 273 := by
    have hcard : (Finset.Icc (19 : ℕ) 57).card = 39 := by decide
    apply le_trans (Finset.sum_le_card_nsmul _ _ 7 _)
    · simp [hcard]
    · intro k hk
      simp only [Finset.mem_Icc] at hk
      have hkr : r + (k : ℝ) / 100 < 8 := by
        have : (k : ℝ) ≤ 57 := by exact_mod_cast hk.2
        linarith
      have := Int.floor_lt.mpr (show r + (k : ℝ) / 100 < (8 : ℤ) by exact_mod_cast hkr)
      omega
  have h2 : ∑ k ∈ Finset.Icc (58 : ℕ) 91, ⌊r + k / 100⌋ ≤ 272 := by
    have hcard : (Finset.Icc (58 : ℕ) 91).card = 34 := by decide
    apply le_trans (Finset.sum_le_card_nsmul _ _ 8 _)
    · simp [hcard]
    · intro k hk
      simp only [Finset.mem_Icc] at hk
      have hkr : r + (k : ℝ) / 100 < 9 := by
        have : (k : ℝ) ≤ 91 := by exact_mod_cast hk.2
        linarith
      have := Int.floor_lt.mpr (show r + (k : ℝ) / 100 < (9 : ℤ) by exact_mod_cast hkr)
      omega
  linarith

end Problems.Minif2f.aime_1991_p6
