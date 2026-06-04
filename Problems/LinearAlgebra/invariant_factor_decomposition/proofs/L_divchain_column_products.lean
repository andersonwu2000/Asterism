import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- entry_kind: Builder
-- divchain_column_products: column products with per-prime non-decreasing exponents
-- form a divisibility chain via Finset.prod_dvd_prod_of_dvd + pow_dvd_pow per prime.
theorem divchain_column_products {K : Type*} [Field K] {r s : ℕ}
    (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ)
    (hc : ∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) :
    ∀ i j : Fin r, i ≤ j → (∏ t, q t ^ c i t) ∣ (∏ t, q t ^ c j t) := by
  intro i j h
  apply Finset.prod_dvd_prod_of_dvd
  intro t _
  exact pow_dvd_pow (q t) (hc i j h t)

end Problems.LinearAlgebra.invariant_factor_decomposition

