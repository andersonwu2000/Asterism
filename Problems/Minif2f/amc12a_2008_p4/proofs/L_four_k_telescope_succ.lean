import Mathlib
import Problems.Minif2f.amc12a_2008_p4.Defs

namespace Problems.Minif2f.amc12a_2008_p4

-- four_k_telescope_succ: inductive step — split off last Icc term via prod_insert,
-- apply IH, then close with field_simp after establishing the non-zero divisor.
theorem four_k_telescope_succ :
    ∀ n : ℕ,
      (∏ k ∈ Finset.Icc (1 : ℕ) n, ((4 : ℝ) * k + 4) / (4 * k)) = (n : ℝ) + 1 →
      (∏ k ∈ Finset.Icc (1 : ℕ) (n + 1), ((4 : ℝ) * k + 4) / (4 * k)) =
        ((n + 1 : ℕ) : ℝ) + 1 := by
  intro n ih
  have key : Finset.Icc (1 : ℕ) (n + 1) = insert (n + 1) (Finset.Icc 1 n) := by
    ext x; simp only [Finset.mem_insert, Finset.mem_Icc]; omega
  have hmem : (n + 1) ∉ Finset.Icc (1 : ℕ) n := by
    simp only [Finset.mem_Icc]; omega
  rw [key, Finset.prod_insert hmem, ih]
  push_cast
  have h1 : (4 : ℝ) * (↑n + 1) ≠ 0 := by positivity
  field_simp

end Problems.Minif2f.amc12a_2008_p4
