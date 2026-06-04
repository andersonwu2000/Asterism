import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- entry_kind: Backward
theorem directsum_reindex_padded {K : Type*} [Field K] {ι : Type*} [Fintype ι]
    {r s : ℕ} (p : ι → Polynomial K) (e : ι → ℕ)
    (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ)
    (idx : ι → Fin r × Fin s)
    (hinj : Function.Injective idx)
    (hmatch : ∀ i, p i ^ e i = q (idx i).2 ^ c (idx i).1 (idx i).2)
    (hpad : ∀ k t, (∀ i, idx i ≠ (k, t)) → c k t = 0) :
    Nonempty (DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i})
      ≃ₗ[Polynomial K]
      DirectSum (Fin r) (fun k => DirectSum (Fin s)
        (fun t => Polynomial K ⧸ Submodule.span (Polynomial K) {q t ^ c k t}))) := by sorry

end Problems.LinearAlgebra.invariant_factor_decomposition
