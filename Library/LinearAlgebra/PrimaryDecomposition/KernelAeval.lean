import Mathlib

namespace Library.LinearAlgebra.PrimaryDecomposition.KernelAeval

-- entry_kind: Builder
-- ker_aeval_le_of_dvd: kernel inclusion under polynomial divisibility
-- p ∣ r means r = q*p for some q; aeval T r = aeval T q ∘ aeval T p,
-- so any v annihilated by aeval T p is annihilated by aeval T r.
theorem ker_aeval_le_of_dvd
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) (p r : Polynomial K) (h : p ∣ r) :
    LinearMap.ker (Polynomial.aeval T p) ≤ LinearMap.ker (Polynomial.aeval T r) := by
  intro v hv
  simp only [LinearMap.mem_ker] at *
  obtain ⟨q, hq⟩ := h
  rw [hq, mul_comm, map_mul, Module.End.mul_apply, hv, map_zero]

-- Direct induction on n (no sub-goals; leaf-bypass).
-- Peel q 0 off the product via `Fin.prod_univ_succ`; q 0 is coprime to the tail
-- ∏ q i.succ (pairwise coprimality + `IsCoprime.prod_right`), so the 2-factor
-- `Polynomial.sup_ker_aeval_eq_ker_aeval_mul_of_coprime` splits the kernel into
-- ker(aeval T (q 0)) ⊔ ker(aeval T (tail)); the IH bounds the tail kernel.
theorem ker_aeval_prod_le_isup_ker_aeval
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) :
    LinearMap.ker (Polynomial.aeval T (∏ i, q i)) ≤
      ⨆ i, LinearMap.ker (Polynomial.aeval T (q i))  := by
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

-- coprime_q_prod_erase: IsCoprime q i with product over erase i, from pairwise coprimality
-- Uses IsCoprime.prod_right_iff to reduce to per-factor coprimality, then hcop.
theorem coprime_q_prod_erase
    {K : Type*} [Field K] {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) (i : Fin n) :
    IsCoprime (q i) (∏ j ∈ Finset.univ.erase i, q j) := by
  rw [IsCoprime.prod_right_iff]
  intro j hj
  exact hcop ((Finset.mem_erase.mp hj).1).symm

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

-- ⨆ ker(aeval T qᵢ) ≤ ker(aeval T ∏qⱼ): pure divisibility, no coprimality.
-- iSup_le reduces to a per-factor inclusion; each qᵢ ∣ ∏qⱼ (Finset.dvd_prod_of_mem),
-- and ker(aeval T ·) is monotone under polynomial divisibility (ker_aeval_le_of_dvd).
theorem isup_ker_aeval_le_ker_aeval_prod
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K) :
    ⨆ i, LinearMap.ker (Polynomial.aeval T (q i)) ≤
      LinearMap.ker (Polynomial.aeval T (∏ i, q i))  := by
  apply iSup_le
  intro i
  have hdvd : q i ∣ ∏ j, q j := Finset.dvd_prod_of_mem q (Finset.mem_univ i)
  exact ker_aeval_le_of_dvd T (q i) (∏ j, q j) hdvd

-- `iSupIndep` of the kernels reduces (via `iSupIndep_def`) to per-`i` disjointness
-- of `ker (aeval T (q i))` from the join of the others. The join is bounded above
-- by `ker (aeval T (∏_{j≠i} q j))` (h_le), and `q i` is coprime to that product
-- (h_cop, from pairwise coprimality); `disjoint_ker_aeval_of_isCoprime` + `mono_right`
-- then close it. Both sub-goals are single-`i` facts, strictly simpler than the n-fold
-- independence.
theorem ker_aeval_isupindep_of_pairwise_coprime
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) :
    iSupIndep (fun i => LinearMap.ker (Polynomial.aeval T (q i)))  := by
  rw [iSupIndep_def]
  intro i
  have h_le := sup_ker_le_ker_prod T q i
  have h_cop := coprime_q_prod_erase q hcop i
  exact (Polynomial.disjoint_ker_aeval_of_isCoprime T h_cop).mono_right h_le

-- n-factor coprime kernel-decomposition: ⨆ ker(aeval T qᵢ) = ker(aeval T ∏qᵢ).
-- Split by `le_antisymm` into the two inclusions:
--   • h_le : ⨆ ≤ ker(prod) — pure divisibility (qᵢ ∣ ∏), no coprimality needed;
--   • h_ge : ker(prod) ≤ ⨆ — the coprime n-factor induction (uses hcop).
theorem isup_ker_aeval_eq_ker_aeval_prod
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) :
    ⨆ i, LinearMap.ker (Polynomial.aeval T (q i)) = LinearMap.ker (Polynomial.aeval T (∏ i, q i))  := by
  apply le_antisymm
  · exact isup_ker_aeval_le_ker_aeval_prod T q
  · exact ker_aeval_prod_le_isup_ker_aeval T q hcop

-- Internal-direct-sum decomposition V = ⊕ ker(aeval T (q i)) for pairwise
-- coprime qᵢ, reduced via `isInternal_submodule_of_iSupIndep_of_iSup_eq_top`
-- to its two premises:
--   • h_indep : the kernels are `iSupIndep` (n-factor independence built from
--     pairwise coprimality of the qᵢ);
--   • h_sup   : their join equals ker(aeval T (∏ qᵢ)) (n-factor coprime
--     kernel-decomposition), which is ⊤ by `htop`.
-- Both sub-goals are strictly simpler n-factor inductions; the parent is then
-- a pure two-premise assembly via the combinator.
theorem is_internal_ker_aeval_of_pairwise_coprime
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j)))
    (htop : LinearMap.ker (Polynomial.aeval T (∏ i, q i)) = ⊤) :
    DirectSum.IsInternal (fun i => LinearMap.ker (Polynomial.aeval T (q i)))  := by
  have h_indep : iSupIndep (fun i => LinearMap.ker (Polynomial.aeval T (q i))) :=
    ker_aeval_isupindep_of_pairwise_coprime T q hcop
  have h_sup : ⨆ i, LinearMap.ker (Polynomial.aeval T (q i))
      = LinearMap.ker (Polynomial.aeval T (∏ i, q i)) :=
    isup_ker_aeval_eq_ker_aeval_prod T q hcop
  exact DirectSum.isInternal_submodule_of_iSupIndep_of_iSup_eq_top h_indep (h_sup.trans htop)

end Library.LinearAlgebra.PrimaryDecomposition.KernelAeval
