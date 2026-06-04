import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs

namespace Problems.Minif2f.imo_1979_p1

-- sum_recip_eq_witness_div_prod: 1/f(j) terms combine via mul_prod_erase
-- Each 1/f(j) = (∏ s.erase j) / (∏ s) since f(j) * ∏ s.erase j = ∏ s.
theorem sum_recip_eq_witness_div_prod (f : ℕ → ℕ) (s : Finset ℕ)
    (hpos : ∀ j ∈ s, 0 < f j) :
    (∑ j ∈ s, (1 : ℝ) / ((f j : ℕ) : ℝ)) =
      ((∑ j ∈ s, ∏ k ∈ s.erase j, f k : ℕ) : ℝ) /
        ((∏ j ∈ s, f j : ℕ) : ℝ) := by
  have hfne : ∀ j ∈ s, (f j : ℝ) ≠ 0 := fun j hj =>
    Nat.cast_ne_zero.mpr (hpos j hj).ne'
  have hprod_ne : ∏ k ∈ s, (f k : ℝ) ≠ 0 :=
    (Finset.prod_pos (fun j hj => by exact_mod_cast hpos j hj)).ne'
  push_cast [Nat.cast_sum, Nat.cast_prod]
  rw [Finset.sum_div]
  apply Finset.sum_congr rfl
  intro j hj
  have hmul : (f j : ℝ) * ∏ k ∈ s.erase j, (f k : ℝ) = ∏ k ∈ s, (f k : ℝ) :=
    Finset.mul_prod_erase s (fun k => (f k : ℝ)) hj
  rw [div_eq_div_iff (hfne j hj) hprod_ne, one_mul, ← hmul, mul_comm]

end Problems.Minif2f.imo_1979_p1
