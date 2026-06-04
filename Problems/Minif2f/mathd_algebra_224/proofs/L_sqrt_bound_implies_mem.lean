import Mathlib
namespace Problems.Minif2f.mathd_algebra_224

-- sqrt_bound_implies_mem: square both sides via sq_sqrt + nlinarith to get ℕ bounds, then omega
theorem sqrt_bound_implies_mem : ∀ n : ℕ,
    (Real.sqrt (n : ℝ) < 7/2 ∧ 2 < Real.sqrt (n : ℝ)) →
    n ∈ ({5,6,7,8,9,10,11,12} : Finset ℕ) := by
  intro n ⟨h1, h2⟩
  have hnn : (0 : ℝ) ≤ n := Nat.cast_nonneg n
  have hsq := Real.sq_sqrt hnn
  have hge : (0 : ℝ) ≤ Real.sqrt n := Real.sqrt_nonneg n
  have hn_lt : (n : ℝ) < 49/4 := by nlinarith [sq_nonneg (Real.sqrt n - 7/2)]
  have hn_gt : (4 : ℝ) < n := by nlinarith [sq_nonneg (Real.sqrt n - 2)]
  have hn1 : n < 13 := by exact_mod_cast show (n : ℝ) < 13 by linarith
  have hn2 : 4 < n := by exact_mod_cast show (4 : ℝ) < n by linarith
  simp only [Finset.mem_insert, Finset.mem_singleton]
  omega

end Problems.Minif2f.mathd_algebra_224
