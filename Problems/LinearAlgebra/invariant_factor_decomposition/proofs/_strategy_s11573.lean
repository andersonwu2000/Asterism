import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_crt_row_collapse

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Collapse each row's inner CRT sum fibre-wise, then bundle over the rows.
-- h_crt (sub-goal `crt_row_collapse`): for pairwise-coprime g, the inner sum
--   ⨁ᵢ K[X]/(g i) is K[X]-linearly iso to K[X]/(∏ᵢ g i).
-- Apply it per row k with g := fun t => q t ^ c k t (coprimality of the powers
--   from `hcop` via `IsCoprime.pow`); bundle the per-row equivs with
--   `DirectSum.congrLinearEquiv`.
theorem s11573 {K : Type*} [Field K] {r s : ℕ}
    (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ)
    (hcop : ∀ t t', t ≠ t' → IsCoprime (q t) (q t')) :
    Nonempty (DirectSum (Fin r) (fun k => DirectSum (Fin s)
          (fun t => Polynomial K ⧸ Submodule.span (Polynomial K) {q t ^ c k t}))
        ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun k =>
          Polynomial K ⧸ Submodule.span (Polynomial K) {∏ t, q t ^ c k t}))  := by
  refine ⟨DirectSum.congrLinearEquiv (fun k => ?_)⟩
  exact (crt_row_collapse (fun t => q t ^ c k t)
    (fun t t' h => (hcop t t' h).pow)).some

end Problems.LinearAlgebra.invariant_factor_decomposition

