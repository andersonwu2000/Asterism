import Mathlib
import Problems.Minif2f.mathd_numbertheory_109.Defs

namespace Problems.Minif2f.mathd_numbertheory_109

-- Direct leaf proof: substitute v k = 2*k-1, then ∑_{k=1}^{n} (2k-1) = n² by induction.
-- For n = 100 the sum is 10000 and 10000 % 7 = 4 (closed by `rw`'s auto-rfl).
theorem s519 : ∀ (v : ℕ → ℕ) (h₀ : ∀ n, v n = 2 * n - 1),
    (∑ k ∈ Finset.Icc 1 100, v k) % 7 = 4  := by
  intro v h₀
  have hv : ∀ k ∈ Finset.Icc 1 100, v k = 2 * k - 1 := fun k _ => h₀ k
  rw [Finset.sum_congr rfl hv]
  have aux : ∀ n, ∑ k ∈ Finset.Icc 1 n, (2 * k - 1) = n * n := by
    intro n
    induction n with
    | zero => decide
    | succ n ih =>
      rw [Finset.sum_Icc_succ_top (by omega : 1 ≤ n + 1)]
      rw [ih]
      have h2 : 2 * (n + 1) - 1 = 2 * n + 1 := by omega
      rw [h2]; ring
  rw [aux 100]

end Problems.Minif2f.mathd_numbertheory_109
