import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- entry_kind: Backward
theorem exists_grid_reindex {K : Type*} [Field K] {ι : Type*} [Fintype ι]
    (p : ι → Polynomial K) (e : ι → ℕ) (hirr : ∀ i, Irreducible (p i))
    (hmon : ∀ i, (p i).Monic) :
    ∃ (r s : ℕ) (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ)
      (idx : ι → Fin r × Fin s),
      (∀ t, (q t).Monic) ∧
      (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
      (∀ k, ¬ IsUnit (∏ t, q t ^ c k t)) ∧
      (∀ t t', t ≠ t' → IsCoprime (q t) (q t')) ∧
      Function.Injective idx ∧
      (∀ i, p i ^ e i = q (idx i).2 ^ c (idx i).1 (idx i).2) ∧
      (∀ k t, (∀ i, idx i ≠ (k, t)) → c k t = 0) := by sorry

end Problems.LinearAlgebra.invariant_factor_decomposition
