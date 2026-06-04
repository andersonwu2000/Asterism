import Library.LinearAlgebra.InvariantFactor.DirectSumBasic
import Library.LinearAlgebra.InvariantFactor.GridConstruction
import Library.LinearAlgebra.InvariantFactor.PolynomialCRT
import Library.LinearAlgebra.InvariantFactor.PrimeFactorData
import Mathlib

open Library.LinearAlgebra.InvariantFactor.DirectSumBasic
open Library.LinearAlgebra.InvariantFactor.GridConstruction
open Library.LinearAlgebra.InvariantFactor.PolynomialCRT
open Library.LinearAlgebra.InvariantFactor.PrimeFactorData

namespace Library.LinearAlgebra.InvariantFactor.GridReindex

-- row_nonunit: a product of irreducible powers with at least one positive exponent is not a unit.
-- Extracts the positive-exponent factor via Finset.mul_prod_erase, applies
-- isUnit_of_mul_isUnit_left to conclude the factor would be a unit, then
-- isUnit_pow_iff + Irreducible.not_isUnit gives the contradiction.
-- entry_kind: Builder
theorem row_nonunit {K : Type*} [Field K] (s : ℕ) (q : Fin s → Polynomial K)
    (crow : Fin s → ℕ) (hirr : ∀ t, Irreducible (q t)) (h : ∃ t, 0 < crow t) :
    ¬ IsUnit (∏ t, q t ^ crow t) := by
  obtain ⟨t₀, ht₀⟩ := h
  intro hunit
  have hfact : ∏ t, q t ^ crow t = q t₀ ^ crow t₀ *
      ∏ t ∈ Finset.univ.erase t₀, q t ^ crow t :=
    (Finset.mul_prod_erase _ _ (Finset.mem_univ t₀)).symm
  rw [hfact] at hunit
  have hunit_factor : IsUnit (q t₀ ^ crow t₀) := isUnit_of_mul_isUnit_left hunit
  have hnotunit : ¬IsUnit (q t₀ ^ crow t₀) := by
    rw [isUnit_pow_iff (Nat.pos_iff_ne_zero.mp ht₀)]
    exact (hirr t₀).not_isUnit
  exact hnotunit hunit_factor

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

-- Reindex the prime-power direct sum onto the invariant-factor grid in four moves.
-- `reindex_drop_subsingleton` (applied twice) bijects a direct sum onto an injective
--   sub-index, discarding summands outside the image (here the e i = 0 / padded c = 0
--   cells, which are trivial K[X]/(unit) quotients).  `assoc_quot_lequiv` matches each
--   surviving summand via `hassoc`; `directsum_prod_uncurry` flattens the Fin r × Fin s
--   grid.  Each sub-goal is witness-independent and strictly smaller than the bundle.
theorem reindex_iso {K : Type*} [Field K] {ι : Type*} [Fintype ι]
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

-- Build the invariant-factor grid in two independent moves + one arithmetic leaf.
-- distinct_primes: enumerate the distinct monic irreducible primes q with a column key,
--   giving monic/irreducible/pairwise-coprime and p i = q (key i) (monic ⇒ rep is p i).
-- sorted_grid: pure-ℕ sorting/padding — places each positive exponent e i into row idx,
--   ascending grid c, injective idx over the positive-exponent subtype, padding zeros,
--   and every row has a positive entry (tallest column fills all rows).
-- row_nonunit: a row product of irreducible powers with one positive exponent is no unit.
-- Closer: assemble; cond 6 collapses to Associated.refl after rewriting key/value equalities.
theorem grid_data {K : Type*} [Field K] {ι : Type*} [Fintype ι]
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
theorem prime_power_regroup {K : Type*} [Field K] {ι : Type*} [Fintype ι]
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

-- Collapse each row's inner CRT sum fibre-wise, then bundle over the rows.
-- h_crt (sub-goal `crt_row_collapse`): for pairwise-coprime g, the inner sum
--   ⨁ᵢ K[X]/(g i) is K[X]-linearly iso to K[X]/(∏ᵢ g i).
-- Apply it per row k with g := fun t => q t ^ c k t (coprimality of the powers
--   from `hcop` via `IsCoprime.pow`); bundle the per-row equivs with
--   `DirectSum.congrLinearEquiv`.
theorem directsum_grid_crt {K : Type*} [Field K] {r s : ℕ}
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

-- Recombine prime-power summands into an invariant-factor grid in two moves.
-- h_regroup: construct the grid (distinct monic primes q, ascending exponent grid c,
--   pairwise-coprime q) plus the K[X]-linear iso onto the *double* sum ⨁ₖ⨁ₜ K[X]/(qₜ^cₖₜ)
--   — the witness-bearing crux, but with each summand an individual prime power.
-- h_crt: collapse each column ⨁ₜ K[X]/(qₜ^cₖₜ) ≃ K[X]/(∏ₜ qₜ^cₖₜ) via fibre-wise CRT.
-- Closer: chain the two isos; the arithmetic conditions pass straight through.
theorem recombine_unified {K : Type*} [Field K] {ι : Type*} [Fintype ι]
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

end Library.LinearAlgebra.InvariantFactor.GridReindex
