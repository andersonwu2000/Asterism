import Mathlib
import Problems.Minif2f.aime_1991_p6.Defs

namespace Problems.Minif2f.aime_1991_p6

-- sum_floor_geq_547: split Icc 19..91 at 56; each half bounded below by 7 (resp. 8)
-- via Int.le_floor + push_cast/linarith; constant sums 37*7=259, 36*8=288 closed by decide
theorem sum_floor_geq_547 :
    ∀ (r : ℝ), 744/100 ≤ r → 547 ≤ ∑ k ∈ Finset.Icc (19 : ℕ) 91, Int.floor (r + k / 100) := by
  intro r hr
  have h1 : ∀ k ∈ Finset.Icc (19 : ℕ) 55, (7 : ℤ) ≤ Int.floor (r + k / 100) := fun k hk => by
    rw [Finset.mem_Icc] at hk
    rw [Int.le_floor]
    push_cast
    have hk1 : (19 : ℝ) ≤ k := by exact_mod_cast hk.1
    linarith
  have h2 : ∀ k ∈ Finset.Icc (56 : ℕ) 91, (8 : ℤ) ≤ Int.floor (r + k / 100) := fun k hk => by
    rw [Finset.mem_Icc] at hk
    rw [Int.le_floor]
    push_cast
    have hk1 : (56 : ℝ) ≤ k := by exact_mod_cast hk.1
    linarith
  have split : Finset.Icc (19 : ℕ) 91 = Finset.Icc 19 55 ∪ Finset.Icc 56 91 := by
    ext x; simp [Finset.mem_Icc]; omega
  have disj : Disjoint (Finset.Icc (19 : ℕ) 55) (Finset.Icc 56 91) := by
    apply Finset.disjoint_left.mpr
    intro x hx hy
    simp [Finset.mem_Icc] at hx hy
    omega
  rw [split, Finset.sum_union disj]
  have lb1 : 259 ≤ ∑ k ∈ Finset.Icc (19 : ℕ) 55, Int.floor (r + k / 100) := by
    have hge := Finset.sum_le_sum h1
    have hcard : (∑ _k ∈ Finset.Icc (19 : ℕ) 55, (7 : ℤ)) = 259 := by decide
    linarith
  have lb2 : 288 ≤ ∑ k ∈ Finset.Icc (56 : ℕ) 91, Int.floor (r + k / 100) := by
    have hge := Finset.sum_le_sum h2
    have hcard : (∑ _k ∈ Finset.Icc (56 : ℕ) 91, (8 : ℤ)) = 288 := by decide
    linarith
  linarith

end Problems.Minif2f.aime_1991_p6
