import Library.LinearAlgebra.InvariantFactor.DirectSumBasic
import Library.LinearAlgebra.InvariantFactor.GridConstruction
import Library.LinearAlgebra.InvariantFactor.PolynomialCRT
import Library.LinearAlgebra.InvariantFactor.PrimeFactorData
import Mathlib

open Library.LinearAlgebra.InvariantFactor.DirectSumBasic
open Library.LinearAlgebra.InvariantFactor.GridConstruction
open Library.LinearAlgebra.InvariantFactor.PolynomialCRT
open Library.LinearAlgebra.InvariantFactor.PrimeFactorData

/-!
## Grid reindexing for the invariant factor decomposition

This file reorganises a family of prime-power quotients `K[X]/(pᵢ^eᵢ)` into a
doubly-indexed grid and then collapses it row-by-row via CRT, yielding a direct
sum of cyclic modules `K[X]/(d_k)` where the `d_k` form a divisibility chain.
The key results are `prime_power_regroup` (reindexing into the grid) and
`recombine_unified` (applying CRT to produce the invariant-factor form).
-/

namespace Library.LinearAlgebra.InvariantFactor.GridReindex

variable {K : Type*} [Field K]

/-- A product of irreducible polynomials raised to positive exponents is not a unit.
This ensures that every row of the grid represents a non-trivial cyclic factor. -/
theorem row_nonunit (s : ℕ) (q : Fin s → Polynomial K)
    (crow : Fin s → ℕ) (hirr : ∀ t, Irreducible (q t)) (h : ∃ t, 0 < crow t) :
    ¬ IsUnit (∏ t, q t ^ crow t) := by
  obtain ⟨t₀, ht₀⟩ := h
  intro hunit
  have hnotunit : ¬IsUnit (q t₀ ^ crow t₀) := by
    rw [isUnit_pow_iff (Nat.pos_iff_ne_zero.mp ht₀)]
    exact (hirr t₀).not_isUnit
  exact hnotunit (isUnit_of_dvd_unit
    (Finset.dvd_prod_of_mem (fun t => q t ^ crow t) (Finset.mem_univ t₀)) hunit)

section

variable {ι : Type*} [Fintype ι]

/-- Given a keyed assignment of positive exponents over `Fin s`, there exists a monotone
grid `c : Fin r → Fin s → ℕ` and an injection `idx` placing each element into the grid
such that the grid entries are non-decreasing along rows, every row contains a positive
entry, and `c` agrees with the original exponents at the image of `idx`. -/
-- sorted_grid: closes by citing the proved brick `monotone_grid_of_keyed_exponents`
-- which is an alias for s11585 and has an identical statement.
theorem sorted_grid
    (e : ι → ℕ) (s : ℕ) (key : {i : ι // 0 < e i} → Fin s) :
    ∃ (r : ℕ) (c : Fin r → Fin s → ℕ) (idx : {i : ι // 0 < e i} → Fin r × Fin s),
      (∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) ∧
      Function.Injective idx ∧
      (∀ i, (idx i).2 = key i) ∧
      (∀ i, c (idx i).1 (idx i).2 = e i.val) ∧
      (∀ k, ∃ t, 0 < c k t) ∧
      (∀ k t, (∀ i, idx i ≠ (k, t)) → c k t = 0) := by
  exact monotone_grid_of_keyed_exponents e s key

/-- Given a grid of exponents and an injection `idx` that places each prime-power factor
`p i ^ e i` into an associated grid entry `q (idx i).2 ^ c (idx i).1 (idx i).2`, this
constructs a linear equivalence between the direct sum over `ι` and the nested direct sum
over the grid `Fin r × Fin s`, dropping trivial (subsingleton) summands along the way. -/
theorem reindex_iso
    (p : ι → Polynomial K) (e : ι → ℕ)
    (r s : ℕ) (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ)
    (idx : {i : ι // 0 < e i} → Fin r × Fin s)
    (hinj : Function.Injective idx)
    (hassoc : ∀ i, Associated (p i.val ^ e i.val) (q (idx i).2 ^ c (idx i).1 (idx i).2))
    (hpad : ∀ k t, (∀ i, idx i ≠ (k, t)) → c k t = 0) :
    Nonempty (DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i})
      ≃ₗ[Polynomial K]
      DirectSum (Fin r) (fun k => DirectSum (Fin s)
        (fun t => Polynomial K ⧸ Submodule.span (Polynomial K) {q t ^ c k t})))  := by
  classical
  obtain ⟨eLHS⟩ := reindex_drop_subsingleton (R := Polynomial K)
      (M := fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i})
      (Subtype.val : {i // 0 < e i} → ι) Subtype.val_injective
      (fun i hi => by
        have he : e i = 0 := by
          rcases Nat.eq_zero_or_pos (e i) with h | h
          · exact h
          · exact absurd rfl (hi ⟨i, h⟩)
        dsimp only
        rw [he, pow_zero]
        exact subsingleton_quot_span_one)
  have eMid :
      DirectSum {i // 0 < e i}
          (fun j => Polynomial K ⧸ Submodule.span (Polynomial K) {p j.val ^ e j.val})
        ≃ₗ[Polynomial K]
      DirectSum {i // 0 < e i}
          (fun j => Polynomial K ⧸ Submodule.span (Polynomial K)
            {q (idx j).2 ^ c (idx j).1 (idx j).2}) :=
    DirectSum.congrLinearEquiv (fun j => (assoc_quot_lequiv (hassoc j)).some)
  obtain ⟨eUncurry⟩ := directsum_prod_uncurry (R := Polynomial K)
      (fun (k : Fin r) (t : Fin s) =>
        Polynomial K ⧸ Submodule.span (Polynomial K) {q t ^ c k t})
  obtain ⟨eRHS⟩ := reindex_drop_subsingleton (R := Polynomial K)
      (M := fun kt : Fin r × Fin s =>
        Polynomial K ⧸ Submodule.span (Polynomial K) {q kt.2 ^ c kt.1 kt.2})
      idx hinj
      (fun kt hkt => by
        have hc : c kt.1 kt.2 = 0 := hpad kt.1 kt.2 hkt
        dsimp only
        rw [hc, pow_zero]
        exact subsingleton_quot_span_one)
  exact ⟨eLHS.trans (eMid.trans (eRHS.symm.trans eUncurry.symm))⟩

/-- Given a family of monic irreducible polynomials with arbitrary positive exponents,
produces a monotone grid of monic, pairwise-coprime irreducibles and exponents, together
with an injection witnessing that the original prime-power factors embed into the grid.
All grid rows are non-unit, and grid entries outside the image of `idx` are zero. -/
theorem grid_data
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

/-- Given a family of monic irreducibles, the direct sum of quotients `K[X]/(pᵢ^eᵢ)` is
linearly isomorphic to a doubly-indexed direct sum over a monotone grid of monic pairwise-coprime
irreducibles, with non-unit row products and non-decreasing exponents across rows. -/
theorem prime_power_regroup
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

/-- For pairwise-coprime polynomials `q t`, the Chinese Remainder Theorem applies row-by-row
to give a linear equivalence between the doubly-indexed direct sum of prime-power quotients
and the singly-indexed direct sum of row-product quotients `K[X]/(∏ t, q t ^ c k t)`. -/
theorem directsum_grid_crt {r s : ℕ}
    (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ)
    (hcop : ∀ t t', t ≠ t' → IsCoprime (q t) (q t')) :
    Nonempty (DirectSum (Fin r) (fun k => DirectSum (Fin s)
          (fun t => Polynomial K ⧸ Submodule.span (Polynomial K) {q t ^ c k t}))
        ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun k =>
          Polynomial K ⧸ Submodule.span (Polynomial K) {∏ t, q t ^ c k t}))  := by
  refine ⟨DirectSum.congrLinearEquiv (fun k => ?_)⟩
  exact (Library.LinearAlgebra.InvariantFactor.PolynomialCRT.crt_directsum_prod_quot (fun t => q t ^ c k t)
    (fun t t' h => (hcop t t' h).pow)).some

/-- Monotonicity of the grid exponents implies a divisibility chain on the row products:
if `i ≤ j` then `∏ t, q t ^ c i t` divides `∏ t, q t ^ c j t`. -/
theorem divchain_column_products {r s : ℕ}
    (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ)
    (hc : ∀ i j, i ≤ j → ∀ t, c i t ≤ c j t) :
    ∀ i j : Fin r, i ≤ j → (∏ t, q t ^ c i t) ∣ (∏ t, q t ^ c j t) := by
  intro i j h
  apply Finset.prod_dvd_prod_of_dvd
  intro t _
  exact pow_dvd_pow (q t) (hc i j h t)

/-- Given a family of monic irreducible polynomials, the direct sum of prime-power quotients
`K[X]/(pᵢ^eᵢ)` is linearly isomorphic to a direct sum `⊕_k K[X]/(d_k)` where each `d_k` is
a product of prime powers with respect to a set of monic pairwise-coprime irreducibles,
the `d_k` form a divisibility chain, and none of the `d_k` is a unit. -/
theorem recombine_unified
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

end

end Library.LinearAlgebra.InvariantFactor.GridReindex
