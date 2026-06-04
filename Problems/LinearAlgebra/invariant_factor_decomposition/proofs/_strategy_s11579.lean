import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_distinct_primes
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_row_nonunit
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_sorted_grid

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Build the invariant-factor grid in two independent moves + one arithmetic leaf.
-- distinct_primes: enumerate the distinct monic irreducible primes q with a column key,
--   giving monic/irreducible/pairwise-coprime and p i = q (key i) (monic ⇒ rep is p i).
-- sorted_grid: pure-ℕ sorting/padding — places each positive exponent e i into row idx,
--   ascending grid c, injective idx over the positive-exponent subtype, padding zeros,
--   and every row has a positive entry (tallest column fills all rows).
-- row_nonunit: a row product of irreducible powers with one positive exponent is no unit.
-- Closer: assemble; cond 6 collapses to Associated.refl after rewriting key/value equalities.
theorem s11579 {K : Type*} [Field K] {ι : Type*} [Fintype ι]
    (p : ι → Polynomial K) (e : ι → ℕ) (hirr : ∀ i, Irreducible (p i))
    (hmon : ∀ i, (p i).Monic) :
    ∃ (r s : ℕ) (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ)
      (idx : {i : ι // 0 < e i} → Fin r × Fin s),
      (∀ t, (q t).Monic) ∧
      (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
      (∀ k, ¬ IsUnit (∏ t, q t ^ c k t)) ∧
      (∀ t t', t ≠ t' → IsCoprime (q t) (q t')) ∧
      Function.Injective idx ∧
      (∀ i, Associated (p i.val ^ e i.val) (q (idx i).2 ^ c (idx i).1 (idx i).2)) ∧
      (∀ k t, (∀ i, idx i ≠ (k, t)) → c k t = 0)  := by
  obtain ⟨s, q, key, hmon_q, hirr_q, hcop_q, hkey⟩ := distinct_primes p e hirr hmon
  obtain ⟨r, c, idx, hasc, hinj, hidx2, hval, hpos, hpad⟩ := sorted_grid e s key
  refine ⟨r, s, q, c, idx, hmon_q, hasc, ?_, hcop_q, hinj, ?_, hpad⟩
  · intro k
    exact row_nonunit s q (fun t => c k t) hirr_q (hpos k)
  · intro i
    rw [hval i, hidx2 i, ← hkey i]

end Problems.LinearAlgebra.invariant_factor_decomposition
