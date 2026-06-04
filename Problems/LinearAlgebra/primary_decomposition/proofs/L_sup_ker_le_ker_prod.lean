import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs

namespace Problems.LinearAlgebra.primary_decomposition

-- entry_kind: Builder
-- sup_ker_le_ker_prod: iSup of kernels ker(aeval T (q j)) over j≠i embeds into
-- ker(aeval T (∏_{j≠i} q j)) via divisibility: q j ∣ product, so ker(q j) ≤ ker(product)
-- using le_sup_left.trans sup_ker_aeval_le_ker_aeval_mul after factoring out q j.
theorem sup_ker_le_ker_prod
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K) (i : Fin n) :
    (⨆ (j) (_ : j ≠ i), LinearMap.ker (Polynomial.aeval T (q j))) ≤
      LinearMap.ker (Polynomial.aeval T (∏ j ∈ Finset.univ.erase i, q j)) := by
  apply iSup_le
  intro j
  apply iSup_le
  intro hj
  have hmem : j ∈ Finset.univ.erase i := Finset.mem_erase.mpr ⟨hj, Finset.mem_univ j⟩
  obtain ⟨r, hr⟩ := Finset.dvd_prod_of_mem q hmem
  rw [hr]
  exact le_sup_left.trans Polynomial.sup_ker_aeval_le_ker_aeval_mul

end Problems.LinearAlgebra.primary_decomposition

