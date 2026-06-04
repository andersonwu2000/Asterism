import Mathlib

namespace Library.LinearAlgebra.JordanForm.ChainKernel

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

-- repr_comp_linear: lifts basis-vector identity (d.repr ∘ M ∘ d)_a = (d.repr ∘ d)_b to all w
-- Both coord functionals are K-linear; Basis.ext equates them from the basis-vector hypothesis.
-- entry_kind: Builder
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

-- ker M coords above the chain bottoms vanish: M is a down-shift on the basis d, so
-- coord of w at ⟨t,j⟩ (j≥1) = coord of M w at predecessor ⟨t,i⟩, = 0 since M w = 0.

-- (1) coord_m_eq_coord: per-basis-vector identity d.repr(M(d idx))⟨t,i⟩ = d.repr(d idx)⟨t,j⟩;
-- (2) repr_comp_linear: abstract lift of that identity from basis vectors to all w via Basis.ext.
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

-- Direct: rewrite w = ∑ i, (d.repr w i) • d i (Basis.sum_repr), then Submodule.sum_mem.
-- Per term ⟨t,j⟩: if j = 0 it is a bottom generator (smul_mem + subset_span); if j > 0
-- the coefficient d.repr w ⟨t,j⟩ vanishes by hzero, so the term is 0.
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

-- ker M ≤ span of chain bottoms: a kernel element's basis coords vanish above the bottoms.
-- kernel_coeffs_above_zero: for w with M w = 0, every coord d.repr w ⟨t,j⟩ with j ≥ 1 is 0
--   (M lowers d⟨t,j⟩ to the distinct basis vector d⟨t,j-1⟩, so M w = 0 forces those coords to 0).
-- repr_supported_bottoms_mem_span: a w whose coords vanish above j=0 equals Σ over bottoms,
--   hence lies in span {d⟨t,0⟩ : 0 < l t}. Each piece drops the parent's ≤/dynamics coupling.
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

-- span_bottoms_le_ker: each chain-bottom d⟨t,0⟩ maps to 0 under M (hbot), so the span lies in ker M
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

-- ker M = span of the chain bottoms {d⟨t,0⟩ : 0 < l t}, proved by mutual inclusion.
-- h_ker_le_span: a kernel element has zero coefficients on every j ≥ 1 (those map under
--   M to distinct lower basis vectors d⟨t,j-1⟩ by hshift), so it lies in the bottom span.
-- h_span_le_ker: each generator d⟨t,0⟩ is in ker M directly by hbot. le_antisymm combines.
theorem ker_eq_span_chain_bottoms
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    LinearMap.ker M
      = Submodule.span K (Set.range (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩))  := by
  have h_ker_le_span := ker_le_span_bottoms M d hbot hshift
  have h_span_le_ker := span_bottoms_le_ker M d hbot hshift
  exact le_antisymm h_ker_le_span h_span_le_ker

-- chain_bottoms_li: LinearIndependent.comp on basis d — chain bottoms are an injective
-- subfamily of the Jordan basis, hence LI directly from d.linearIndependent.
-- entry_kind: Builder
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

-- ker M is spanned by the chain bottoms {d⟨t,0⟩ : 0 < l t}, an LI sub-family of basis d.
-- finrank(span) = card of the bottom index = #{t // 0 < l t} = filter card.
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
  have hLI := chain_bottoms_li M d hbot hshift
  have hspan := ker_eq_span_chain_bottoms M d hbot hshift
  rw [hspan, finrank_span_eq_card hLI]
  exact Fintype.card_subtype (fun t : Fin p => 0 < l t)

end Library.LinearAlgebra.JordanForm.ChainKernel
