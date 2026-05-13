import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs
import Problems.Minif2f.aime_1997_p11.proofs.L_cos_minus_sin_eq_sqrt2_sin_complement
import Problems.Minif2f.aime_1997_p11.proofs.L_sum_reindex_complement

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

-- cos x - sin x = √2 · sin(π/4 - x), so ∑ (cos(nπ/180) - sin(nπ/180)) = √2 · ∑ sin((45-n)π/180).
-- (1) cos_minus_sin_eq_sqrt2_sin_complement: pointwise identity cos α - sin α = √2 sin(π/4-α).
-- (2) sum_reindex_complement: the involution n ↦ 45-n permutes Icc 1 44, so sin-sums match.
-- Combine via Finset.sum_sub_distrib + Finset.mul_sum, then linarith to (1+√2)·S_s.
set_option linter.style.longLine false in
theorem s9684 :
    (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.cos (n * π / 180)) =
      (1 + Real.sqrt 2) * (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180))  := by
  have h_diff : ∀ (n : ℕ),
      Real.cos ((n : ℝ) * π / 180) - Real.sin ((n : ℝ) * π / 180) =
      Real.sqrt 2 * Real.sin (((45 : ℝ) - n) * π / 180) :=
    cos_minus_sin_eq_sqrt2_sin_complement
  have h_reindex :
      (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (((45 : ℝ) - n) * π / 180)) =
      (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin ((n : ℝ) * π / 180)) :=
    sum_reindex_complement
  have key :
      (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.cos ((n : ℝ) * π / 180)) -
        (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin ((n : ℝ) * π / 180)) =
      Real.sqrt 2 * (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin ((n : ℝ) * π / 180)) := by
    rw [← Finset.sum_sub_distrib]
    rw [Finset.sum_congr rfl (fun n _ => h_diff n)]
    rw [← Finset.mul_sum]
    rw [h_reindex]
  linarith [key]

end Problems.Minif2f.aime_1997_p11
