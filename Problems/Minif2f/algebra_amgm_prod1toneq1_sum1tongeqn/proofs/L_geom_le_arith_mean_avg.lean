import Mathlib
namespace Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn

-- geom_le_arith_mean_avg: Real.geom_mean_le_arith_mean_weighted with uniform weight 1/n
theorem geom_le_arith_mean_avg : ∀ (x : ℕ → ℝ) (n : ℕ), 0 < n →
    (∀ i ∈ Finset.range n, 0 ≤ x i) →
    Finset.prod (Finset.range n) x = 1 →
    (∏ i ∈ Finset.range n, x i)^((1:ℝ)/n)
      ≤ (1/(n:ℝ)) * ∑ i ∈ Finset.range n, x i := by
  intro x n hn hx _
  have hw_nn : ∀ i ∈ Finset.range n, 0 ≤ (1 / (n : ℝ)) := fun i _ =>
    div_nonneg zero_le_one (Nat.cast_nonneg _)
  have hw_sum : ∑ i ∈ Finset.range n, (1 / (n : ℝ)) = 1 := by
    rw [Finset.sum_const, Finset.card_range, nsmul_eq_mul]
    field_simp
  have amgm :=
    Real.geom_mean_le_arith_mean_weighted (Finset.range n) (fun _ => (1:ℝ)/(n:ℝ)) x
      hw_nn hw_sum hx
  rw [Real.finsetProd_rpow _ _ hx] at amgm
  calc (∏ i ∈ Finset.range n, x i) ^ ((1:ℝ) / (n:ℝ))
      ≤ ∑ i ∈ Finset.range n, (1 / (n:ℝ)) * x i := amgm
    _ = (1 / (n:ℝ)) * ∑ i ∈ Finset.range n, x i := (Finset.mul_sum _ _ _).symm

end Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn
