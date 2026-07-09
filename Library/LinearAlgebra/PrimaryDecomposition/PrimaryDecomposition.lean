import Library.LinearAlgebra.PrimaryDecomposition.PolynomialFactorization
import Mathlib.Algebra.BigOperators.Group.Finset.Piecewise
import Mathlib.Algebra.DirectSum.Module
import Mathlib.FieldTheory.Minpoly.Basic
import Mathlib.Order.SupIndep
import Mathlib.RingTheory.Coprime.Lemmas
import Mathlib.RingTheory.IntegralClosure.Algebra.Basic
import Mathlib.RingTheory.Polynomial.Basic

/-!
# Primary Decomposition of a Linear Endomorphism

Given a finite-dimensional vector space $V$ over a field $K$ and a $K$-linear endomorphism
$T : V →ₗ[K] V$, the **primary decomposition theorem** asserts that $V$ decomposes as a direct
sum of primary components $\ker(p_i(T)^{e_i})$, where $\prod_i p_i^{e_i}$ is the minimal
polynomial of $T$ factored into distinct monic irreducible polynomials.

## Main statements

- `ker_aeval_prod_le_iSup_ker_aeval`: for pairwise coprime polynomials $q_i$,
  $\ker\!\bigl((\prod_i q_i)(T)\bigr) \leq \bigsqcup_i \ker(q_i(T))$.
- `iSup_ker_aeval_eq_ker_aeval_prod`: equality holds under pairwise coprimality.
- `isInternal_ker_aeval_of_pairwise_coprime`: internal direct-sum decomposition of the kernel
  of a product under pairwise coprimality.
- `exists_primary_decomp`: existence of the primary decomposition for any finite-dimensional
  endomorphism.

## Implementation notes

The proof of `ker_aeval_prod_le_iSup_ker_aeval` goes by induction on the number of factors,
peeling off the first factor at each step using the two-factor coprime kernel-splitting lemma
`Polynomial.sup_ker_aeval_eq_ker_aeval_mul_of_coprime`.
-/

open Library.LinearAlgebra.PrimaryDecomposition.PolynomialFactorization

namespace Library.LinearAlgebra.PrimaryDecomposition.PrimaryDecomposition

-- The module path ends in `…PrimaryDecomposition.PrimaryDecomposition`, so the linter fires
-- on every declaration in this namespace; the duplication cannot be removed without violating
-- the namespace fence.
set_option linter.dupNamespace false


/-- If $q_0, \ldots, q_{n-1}$ are pairwise coprime polynomials, then
$\ker\!\bigl((\prod_i q_i)(T)\bigr) \leq \bigsqcup_i \ker(q_i(T))$.
Proved by induction on $n$ using the two-factor decomposition
`Polynomial.sup_ker_aeval_eq_ker_aeval_mul_of_coprime`. -/
theorem ker_aeval_prod_le_iSup_ker_aeval
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) :
    LinearMap.ker (Polynomial.aeval T (∏ i, q i)) ≤
      ⨆ i, LinearMap.ker (Polynomial.aeval T (q i)) := by
  induction n with
  | zero => simp [Module.End.one_eq_id, LinearMap.ker_id]
  | succ n ih =>
    rw [Fin.prod_univ_succ]
    have hco : IsCoprime (q 0) (∏ i : Fin n, q i.succ) := by
      apply IsCoprime.prod_right
      intro i _
      exact hcop (Fin.succ_ne_zero i).symm
    rw [← Polynomial.sup_ker_aeval_eq_ker_aeval_mul_of_coprime T hco]
    apply sup_le
    · exact le_iSup (fun i => LinearMap.ker (Polynomial.aeval T (q i))) 0
    · refine le_trans (ih (fun i => q i.succ) ?_) ?_
      · intro i j hij
        exact hcop (fun h => hij (Fin.succ_injective n h))
      · apply iSup_le
        intro i
        exact le_iSup (fun i => LinearMap.ker (Polynomial.aeval T (q i))) i.succ

/-- For pairwise coprime $q_0, \ldots, q_{n-1}$, the polynomial $q_i$ is coprime to the product
$\prod_{j \neq i} q_j$.  Follows from `IsCoprime.prod_right_iff`. -/
theorem coprime_q_prod_erase
    {K : Type*} [Field K] {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) (i : Fin n) :
    IsCoprime (q i) (∏ j ∈ Finset.univ.erase i, q j) :=
  IsCoprime.prod_right_iff.mpr fun _ hj => hcop ((Finset.mem_erase.mp hj).1).symm

/-- The supremum $\bigsqcup_{j \neq i} \ker(q_j(T))$ is contained in
$\ker\!\bigl((\prod_{j \neq i} q_j)(T)\bigr)$, because each $q_j$ divides the product over
the erased set. -/
theorem iSup_ker_aeval_le_ker_aeval_prod_erase
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

/-- If $p \mid r$ then $\ker(p(T)) \leq \ker(r(T))$: the kernel of `Polynomial.aeval T` is
monotone under polynomial divisibility. -/
theorem ker_aeval_le_of_dvd
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) (p r : Polynomial K) (h : p ∣ r) :
    LinearMap.ker (Polynomial.aeval T p) ≤ LinearMap.ker (Polynomial.aeval T r) := by
  intro v hv
  simp only [LinearMap.mem_ker] at *
  obtain ⟨q, hq⟩ := h
  rw [hq, mul_comm, map_mul, Module.End.mul_apply, hv, map_zero]

/-- The submodules $\ker(q_i(T))$ are independent (i.e. `iSupIndep`) whenever the $q_i$ are
pairwise coprime.  The key step is that each $q_i$ is coprime to the product of the remaining
factors (`coprime_q_prod_erase`), giving disjointness via
`Polynomial.disjoint_ker_aeval_of_isCoprime`. -/
theorem iSupIndep_ker_aeval_of_pairwise_coprime
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) :
    iSupIndep (fun i => LinearMap.ker (Polynomial.aeval T (q i))) := by
  rw [iSupIndep_def]
  intro i
  have h_le := iSup_ker_aeval_le_ker_aeval_prod_erase T q i
  have h_cop := coprime_q_prod_erase q hcop i
  exact (Polynomial.disjoint_ker_aeval_of_isCoprime T h_cop).mono_right h_le

/-- The supremum $\bigsqcup_i \ker(q_i(T))$ is contained in $\ker((\prod_i q_i)(T))$ for any
family of polynomials $q_i$, because each $q_i$ divides the product (no coprimality needed). -/
theorem iSup_ker_aeval_le_ker_aeval_prod
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K) :
    ⨆ i, LinearMap.ker (Polynomial.aeval T (q i)) ≤
      LinearMap.ker (Polynomial.aeval T (∏ i, q i)) := by
  apply iSup_le
  intro i
  exact ker_aeval_le_of_dvd T (q i) (∏ j, q j) (Finset.dvd_prod_of_mem q (Finset.mem_univ i))

/-- For pairwise coprime polynomials $q_i$, the supremum of kernels equals the kernel of the
product: $\bigsqcup_i \ker(q_i(T)) = \ker((\prod_i q_i)(T))$.
The $\leq$ direction is pure divisibility; the $\geq$ direction uses coprimality via
`ker_aeval_prod_le_iSup_ker_aeval`. -/
theorem iSup_ker_aeval_eq_ker_aeval_prod
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) :
    ⨆ i, LinearMap.ker (Polynomial.aeval T (q i)) =
      LinearMap.ker (Polynomial.aeval T (∏ i, q i)) := by
  apply le_antisymm
  · exact iSup_ker_aeval_le_ker_aeval_prod T q
  · exact ker_aeval_prod_le_iSup_ker_aeval T q hcop

/-- If the $q_i$ are pairwise coprime and $\ker((\prod_i q_i)(T)) = \top$, then the kernels
$\ker(q_i(T))$ give an internal direct-sum decomposition of the whole space.  Combines
`iSupIndep_ker_aeval_of_pairwise_coprime` with `iSup_ker_aeval_eq_ker_aeval_prod`. -/
theorem isInternal_ker_aeval_of_pairwise_coprime
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j)))
    (htop : LinearMap.ker (Polynomial.aeval T (∏ i, q i)) = ⊤) :
    DirectSum.IsInternal (fun i => LinearMap.ker (Polynomial.aeval T (q i))) := by
  exact DirectSum.isInternal_submodule_of_iSupIndep_of_iSup_eq_top
    (iSupIndep_ker_aeval_of_pairwise_coprime T q hcop)
    ((iSup_ker_aeval_eq_ker_aeval_prod T q hcop).trans htop)

/-- **Primary decomposition**: for every finite-dimensional $K$-linear endomorphism
$T : V →ₗ[K] V$ there exist $n : ℕ$, distinct monic irreducible polynomials $p_0, \ldots, p_{n-1}$,
and positive exponents $e_0, \ldots, e_{n-1}$ such that
$\operatorname{minpoly}_K(T) = \prod_i p_i^{e_i}$ and $V$ is the internal direct sum
$V = \bigoplus_i \ker(p_i(T)^{e_i})$.
The factorization of the minimal polynomial is supplied by `exists_finpow_factorization`; the
kernel decomposition follows from `isInternal_ker_aeval_of_pairwise_coprime`. -/
theorem exists_primary_decomp : ∀ {K : Type*} [Field K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ (n : ℕ) (p : Fin n → Polynomial K) (e : Fin n → ℕ),
    (∀ i, Irreducible (p i)) ∧
    (∀ i, (p i).Monic) ∧
    (∀ i, 0 < e i) ∧
    Function.Injective p ∧
    minpoly K T = ∏ i, p i ^ e i ∧
    DirectSum.IsInternal
      (fun i : Fin n => LinearMap.ker ((Polynomial.aeval T) (p i ^ e i))) := by
  intro K _ V _ _ _ T
  have hT_int : IsIntegral K T := Algebra.IsIntegral.isIntegral T
  have hmonic : (minpoly K T).Monic := minpoly.monic hT_int
  have hne : minpoly K T ≠ 0 := minpoly.ne_zero hT_int
  obtain ⟨n, p, e, hirr, hmono, hpos, hinj, hcop_p, hfact⟩ :=
    exists_finpow_factorization (minpoly K T) hmonic hne
  exact ⟨n, p, e, hirr, hmono, hpos, hinj, hfact,
    isInternal_ker_aeval_of_pairwise_coprime T (fun i => p i ^ e i)
      (fun _ _ hij => (hcop_p _ _ hij).pow)
      (by rw [← hfact, minpoly.aeval K T]; exact LinearMap.ker_zero)⟩

end Library.LinearAlgebra.PrimaryDecomposition.PrimaryDecomposition
