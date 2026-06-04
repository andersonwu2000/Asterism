import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_grid_data
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_reindex_iso

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Regroup prime-power summands into the invariant-factor grid in two separable moves.
-- grid_data: pure combinatorics/arithmetic — distinct monic primes q, ascending exponent
--   grid c (pairwise-coprime, non-unit columns) PLUS an injective reindexing
--   idx : {i // 0 < e i} → Fin r × Fin s matching each pᵢ^eᵢ to its grid cell (over the
--   POSITIVE-exponent subtype, fixing s11574's e i = 0 counterexample) with off-image
--   cells padded to exponent 0.  No module theory.
-- reindex_iso: the witness-INDEPENDENT module iso, fed the reindexing data (idx, hinj,
--   hassoc, hpad) explicitly so it can biject support summands and drop trivial ones
--   (this is what s11574's data-less `directsum_reindex_padded` lacked when it shelved).
-- Closer: the four arithmetic conditions pass straight through; the iso is reindex_iso.
theorem s11577 {K : Type*} [Field K] {ι : Type*} [Fintype ι]
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
  obtain ⟨r, s, q, c, idx, hmonq, hmono, hnu, hcop, hinj, hassoc, hpad⟩ :=
    grid_data p e hirr hmon
  exact ⟨r, s, q, c, hmonq, hmono, hnu, hcop,
    reindex_iso p e r s q c idx hinj hassoc hpad⟩

end Problems.LinearAlgebra.invariant_factor_decomposition
