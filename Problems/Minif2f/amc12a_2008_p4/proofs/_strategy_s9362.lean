import Mathlib
import Problems.Minif2f.amc12a_2008_p4.Defs

namespace Problems.Minif2f.amc12a_2008_p4

-- Direct induction on `n`. Base case: empty product. Successor: split off last term via
-- `Finset.prod_insert` after rewriting `Icc 1 (n+1) = insert (n+1) (Icc 1 n)`, apply IH,
-- simplify with `field_simp` (the `(4:ℝ)*(n+1)` divisor is nonzero by `positivity`).
theorem s9362 : ∀ (n : ℕ),
    (∏ k ∈ Finset.Icc (1 : ℕ) n, ((4 : ℝ) * k + 4) / (4 * k)) = (n : ℝ) + 1  := by
  intro n
  induction n with
  | zero => norm_num
  | succ n ih =>
    have key : Finset.Icc (1 : ℕ) (n + 1) = insert (n + 1) (Finset.Icc 1 n) := by
      ext x; simp only [Finset.mem_insert, Finset.mem_Icc]; omega
    have hmem : (n + 1) ∉ Finset.Icc (1 : ℕ) n := by
      simp only [Finset.mem_Icc]; omega
    rw [key, Finset.prod_insert hmem, ih]
    push_cast
    have h1 : (4 : ℝ) * (↑n + 1) ≠ 0 := by positivity
    field_simp

end Problems.Minif2f.amc12a_2008_p4
