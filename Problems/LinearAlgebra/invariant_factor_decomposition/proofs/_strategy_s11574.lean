import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_directsum_reindex_padded
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_exists_grid_reindex

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Split the witness-bearing crux into combinatorics + module bookkeeping.
-- exists_grid_reindex: build the grid data (distinct monic primes q, ascending exponent
--   grid c, pairwise-coprime q, non-unit column products) PLUS an injective reindexing
--   idx : ι → Fin r × Fin s matching each pᵢ^eᵢ to its grid cell and padding off-image
--   cells with exponent 0 — pure combinatorics/arithmetic, no module theory.
-- directsum_reindex_padded: the witness-independent module iso ⨁ᵢ K[X]/(pᵢ^eᵢ) ≃
--   ⨁ₖ⨁ₜ K[X]/(qₜ^cₖₜ) from the reindexing data (image cells biject with ι, padded
--   cells are trivial K[X]/⊤).
theorem s11574 {K : Type*} [Field K] {ι : Type*} [Fintype ι]
    (p : ι → Polynomial K) (e : ι → ℕ) (hirr : ∀ i, Irreducible (p i))
    (hmon : ∀ i, (p i).Monic) :
    ∃ (r s : ℕ) (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ),
      (∀ t, (q t).Monic) ∧
      (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
      (∀ k, ¬ IsUnit (∏ t, q t ^ c k t)) ∧
      (∀ t t', t ≠ t' → IsCoprime (q t) (q t')) ∧
      Nonempty (DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i})
        ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun k => DirectSum (Fin s)
          (fun t => Polynomial K ⧸ Submodule.span (Polynomial K) {q t ^ c k t})))  := by
  obtain ⟨r, s, q, c, idx, hqmon, hasc, hnu, hcop, hinj, hmatch, hpad⟩ :=
    exists_grid_reindex p e hirr hmon
  exact ⟨r, s, q, c, hqmon, hasc, hnu, hcop,
    directsum_reindex_padded p e q c idx hinj hmatch hpad⟩

end Problems.LinearAlgebra.invariant_factor_decomposition
