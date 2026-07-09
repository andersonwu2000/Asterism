import Mathlib

/-!
# Kernel of a Jordan-chain map equals the span of chain bottoms

Given a basis `d` indexed by Jordan chains `(t, j)` on which `M` acts as a backward shift
(sending `d⟨t,j⟩` to `d⟨t,j-1⟩` for `j ≥ 1` and killing every `d⟨t,0⟩`), this file proves
that `LinearMap.ker M` equals the `K`-span of the chain-bottom vectors `{d⟨t,0⟩ : 0 < l t}`,
and deduces that the finrank of the kernel equals the number of Jordan chains.
-/

namespace Library.LinearAlgebra.JordanForm.ChainKernel

/-- For a Jordan-chain basis where `M` kills bottoms and shifts upper vectors down, the basis
coordinate `d.repr (M (d idx)) ⟨t, i⟩` equals `d.repr (d idx) ⟨t, j⟩` for every basis index,
where `i + 1 = j` is the predecessor relation in the chain. -/
theorem coord_m_eq_coord
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩)
    (t : Fin p) (j i : Fin (l t)) (hij : (i : ℕ) + 1 = (j : ℕ))
    (hMij : M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    ∀ idx : (Σ t : Fin p, Fin (l t)), d.repr (M (d idx)) ⟨t, i⟩ = d.repr (d idx) ⟨t, j⟩ := by
  rintro ⟨t', j'⟩
  rw [Module.Basis.repr_self_apply]
  rcases Nat.eq_zero_or_pos (j' : ℕ) with h0 | hpos
  · have hne : ¬ ((⟨t', j'⟩ : Σ t : Fin p, Fin (l t)) = ⟨t, j⟩) := by
      intro heq
      have h2 : (j' : ℕ) = (j : ℕ) := congrArg (fun x => (x.2 : ℕ)) heq
      omega
    simp [hbot t' j' h0, hne]
  · obtain ⟨i', hi', hMi'⟩ := hshift t' j' hpos
    rw [hMi', Module.Basis.repr_self_apply]
    rcases eq_or_ne t' t with ht | ht
    · subst ht
      have hcond : ((⟨t', i'⟩ : Σ t : Fin p, Fin (l t)) = ⟨t', i⟩) ↔
          ((⟨t', j'⟩ : Σ t : Fin p, Fin (l t)) = ⟨t', j⟩) := by
        simp only [Sigma.mk.injEq, heq_eq_eq, Fin.ext_iff]
        constructor <;> rintro ⟨h1, h2⟩ <;> exact ⟨h1, by omega⟩
      simp only [hcond]
    · have hne1 : ¬ ((⟨t', i'⟩ : Σ t : Fin p, Fin (l t)) = ⟨t, i⟩) :=
        fun heq => ht (congrArg Sigma.fst heq)
      have hne2 : ¬ ((⟨t', j'⟩ : Σ t : Fin p, Fin (l t)) = ⟨t, j⟩) :=
        fun heq => ht (congrArg Sigma.fst heq)
      rw [if_neg hne1, if_neg hne2]

/-- If `d.repr (M (d idx)) a = d.repr (d idx) b` holds for every basis vector `d idx`, then
it holds for every `w : R`; both sides are `K`-linear and `Basis.ext` reduces equality to
basis vectors. -/
theorem repr_comp_linear
    {K R ι : Type*} [Field K] [AddCommGroup R] [Module K R]
    (M : R →ₗ[K] R) (d : Module.Basis ι K R) (a b : ι)
    (h : ∀ idx : ι, d.repr (M (d idx)) a = d.repr (d idx) b) :
    ∀ w : R, d.repr (M w) a = d.repr w b := by
  intro w
  suffices h' : ((Finsupp.lapply a).comp (d.repr.toLinearMap.comp M) : R →ₗ[K] K) =
               (Finsupp.lapply b).comp d.repr.toLinearMap from
    congr_fun (congr_arg DFunLike.coe h') w
  apply d.ext
  intro idx
  simp [h idx]

/-- For any `w` in the kernel of `M`, every basis coordinate `d.repr w ⟨t, j⟩` with `j ≥ 1`
vanishes: the shift hypothesis identifies that coordinate with `d.repr (M w) ⟨t, i⟩ = 0`. -/
theorem kernel_coeffs_above_zero
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩)
    (w : R) (hw : M w = 0) :
    ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) → d.repr w ⟨t, j⟩ = 0  := by
  intro t j hj
  obtain ⟨i, hij, hMij⟩ := hshift t j hj
  have hbasis := coord_m_eq_coord M d hbot hshift t j i hij hMij
  have htransfer := repr_comp_linear M d ⟨t, i⟩ ⟨t, j⟩ hbasis w
  rw [hw, map_zero, Finsupp.zero_apply] at htransfer
  exact htransfer.symm

/-- If every basis coordinate of `w` at a non-bottom position `j ≥ 1` is zero, then `w` lies
in the span of the chain bottoms `{d⟨t,0⟩ : 0 < l t}`.  The proof expands `w = ∑ (d.repr w i) • d i`
and observes that only bottom-index terms can be non-zero. -/
theorem repr_supported_bottoms_mem_span
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩)
    (w : R)
    (hzero : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) → d.repr w ⟨t, j⟩ = 0) :
    w ∈ Submodule.span K
      (Set.range (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩))  := by
  have key : ∀ i : Σ t : Fin p, Fin (l t),
      d.repr w i • d i ∈ Submodule.span K
        (Set.range (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩)) := by
    rintro ⟨t, j⟩
    rcases Nat.eq_zero_or_pos (j : ℕ) with hj | hj
    · have hlt : 0 < l t := lt_of_le_of_lt (Nat.zero_le _) j.isLt
      apply Submodule.smul_mem
      apply Submodule.subset_span
      refine ⟨⟨t, hlt⟩, ?_⟩
      have hjeq : (⟨0, hlt⟩ : Fin (l t)) = j := Fin.ext hj.symm
      simp only [hjeq]
    · rw [hzero t j hj, zero_smul]
      exact Submodule.zero_mem _
  rw [show w = ∑ i, d.repr w i • d i from (d.sum_repr w).symm]
  exact Submodule.sum_mem _ fun i _ => key i

/-- The kernel of `M` is contained in the span of the chain bottoms `{d⟨t,0⟩ : 0 < l t}`:
any kernel element has zero coordinates at every non-bottom index (by `kernel_coeffs_above_zero`),
so it is a linear combination of chain-bottom vectors (by `repr_supported_bottoms_mem_span`). -/
theorem ker_le_span_bottoms
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    LinearMap.ker M
      ≤ Submodule.span K (Set.range (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩)) := by
  intro w hw
  rw [LinearMap.mem_ker] at hw
  have h_coeffs := kernel_coeffs_above_zero M d hbot hshift w hw
  exact repr_supported_bottoms_mem_span M d hbot hshift w h_coeffs

/-- The span of the chain bottoms `{d⟨t,0⟩ : 0 < l t}` is contained in the kernel of `M`,
since each generator `d⟨t,0⟩` maps to zero under `M` by the hypothesis `hbot`. -/
theorem span_bottoms_le_ker
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    Submodule.span K (Set.range (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩))
      ≤ LinearMap.ker M := by
  apply Submodule.span_le.mpr
  rintro x ⟨t, rfl⟩
  exact LinearMap.mem_ker.mpr (hbot t.1 ⟨0, t.2⟩ rfl)

/-- The kernel of `M` equals the `K`-span of the chain-bottom vectors `{d⟨t,0⟩ : 0 < l t}`.
This is the mutual inclusion of `ker_le_span_bottoms` and `span_bottoms_le_ker`. -/
theorem ker_eq_span_chain_bottoms
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    LinearMap.ker M
      = Submodule.span K (Set.range (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩))  := le_antisymm (ker_le_span_bottoms M d hbot hshift) (span_bottoms_le_ker M d hbot hshift)

/-- The chain-bottom vectors `{d⟨t,0⟩ : 0 < l t}` are linearly independent over `K`, as they
form an injective subfamily of the Jordan basis `d`. -/
theorem chain_bottoms_li
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    LinearIndependent K (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩) := by
  apply d.linearIndependent.comp
      (fun t : {t : Fin p // 0 < l t} => (⟨t.1, ⟨0, t.2⟩⟩ : Σ t : Fin p, Fin (l t)))
  intro a b hab
  simp only [Sigma.mk.inj_iff] at hab
  exact Subtype.ext hab.1

/-- The finrank of `ker M` equals the number of non-empty Jordan chains, i.e., the cardinality of
`{t : Fin p | 0 < l t}`.  The proof identifies `ker M` with the span of the linearly independent
chain-bottom family and applies `finrank_span_eq_card`. -/
theorem jordan_chain_ker_finrank
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    Module.finrank K ↥(LinearMap.ker M)
      = (Finset.univ.filter (fun t : Fin p => 0 < l t)).card  := by
  classical
  rw [ker_eq_span_chain_bottoms M d hbot hshift,
      finrank_span_eq_card (chain_bottoms_li M d hbot hshift)]
  exact Fintype.card_subtype (fun t : Fin p => 0 < l t)

end Library.LinearAlgebra.JordanForm.ChainKernel
