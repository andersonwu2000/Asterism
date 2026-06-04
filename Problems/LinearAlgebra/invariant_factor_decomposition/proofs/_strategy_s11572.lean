import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_directsum_grid_crt
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_prime_power_regroup

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Recombine prime-power summands into an invariant-factor grid in two moves.
-- h_regroup: construct the grid (distinct monic primes q, ascending exponent grid c,
--   pairwise-coprime q) plus the K[X]-linear iso onto the *double* sum ⨁ₖ⨁ₜ K[X]/(qₜ^cₖₜ)
--   — the witness-bearing crux, but with each summand an individual prime power.
-- h_crt: collapse each column ⨁ₜ K[X]/(qₜ^cₖₜ) ≃ K[X]/(∏ₜ qₜ^cₖₜ) via fibre-wise CRT.
-- Closer: chain the two isos; the arithmetic conditions pass straight through.
theorem s11572 {K : Type*} [Field K] {ι : Type*} [Fintype ι]
    (p : ι → Polynomial K) (e : ι → ℕ) (hirr : ∀ i, Irreducible (p i))
    (hmon : ∀ i, (p i).Monic) :
    ∃ (r s : ℕ) (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ),
      (∀ t, (q t).Monic) ∧
      (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
      (∀ k, ¬ IsUnit (∏ t, q t ^ c k t)) ∧
      Nonempty (DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i})
        ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun k => Polynomial K ⧸ Submodule.span (Polynomial K) {∏ t, q t ^ c k t}))  := by
  obtain ⟨r, s, q, c, hmonq, hmonoc, hnu, hcop, ⟨isoA⟩⟩ :
      ∃ (r s : ℕ) (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ),
        (∀ t, (q t).Monic) ∧
        (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
        (∀ k, ¬ IsUnit (∏ t, q t ^ c k t)) ∧
        (∀ t t', t ≠ t' → IsCoprime (q t) (q t')) ∧
        Nonempty (DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i})
          ≃ₗ[Polynomial K]
          DirectSum (Fin r) (fun k => DirectSum (Fin s)
            (fun t => Polynomial K ⧸ Submodule.span (Polynomial K) {q t ^ c k t}))) :=
    prime_power_regroup p e hirr hmon

  obtain ⟨isoB⟩ :
      Nonempty (DirectSum (Fin r) (fun k => DirectSum (Fin s)
            (fun t => Polynomial K ⧸ Submodule.span (Polynomial K) {q t ^ c k t}))
          ≃ₗ[Polynomial K]
          DirectSum (Fin r) (fun k => Polynomial K ⧸ Submodule.span (Polynomial K) {∏ t, q t ^ c k t})) :=
    directsum_grid_crt q c hcop

  exact ⟨r, s, q, c, hmonq, hmonoc, hnu, ⟨isoA.trans isoB⟩⟩


end Problems.LinearAlgebra.invariant_factor_decomposition
