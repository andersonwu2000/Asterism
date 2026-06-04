import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_monotone_grid_of_keyed_exponents

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- sorted_grid: closes by citing the proved brick `monotone_grid_of_keyed_exponents`
-- which is an alias for s11585 and has an identical statement.
theorem sorted_grid {ι : Type*} [Fintype ι]
    (e : ι → ℕ) (s : ℕ) (key : {i : ι // 0 < e i} → Fin s) :
    ∃ (r : ℕ) (c : Fin r → Fin s → ℕ) (idx : {i : ι // 0 < e i} → Fin r × Fin s),
      (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
      Function.Injective idx ∧
      (∀ i, (idx i).2 = key i) ∧
      (∀ i, c (idx i).1 (idx i).2 = e i.val) ∧
      (∀ k, ∃ t, 0 < c k t) ∧
      (∀ k t, (∀ i, idx i ≠ (k, t)) → c k t = 0) := by
  exact monotone_grid_of_keyed_exponents e s key

end Problems.LinearAlgebra.invariant_factor_decomposition