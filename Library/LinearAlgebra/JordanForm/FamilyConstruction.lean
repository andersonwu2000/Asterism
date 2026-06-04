import Library.LinearAlgebra.JordanForm.ChainKernel
import Library.LinearAlgebra.JordanForm.FamilyCoeffs
import Mathlib

open Library.LinearAlgebra.JordanForm.ChainKernel
open Library.LinearAlgebra.JordanForm.FamilyCoeffs

namespace Library.LinearAlgebra.JordanForm.FamilyConstruction

-- entry_kind: Builder
-- inf_ker_restrict_bridge: p ⊓ ker f and ker (f.restrict hf) have the same finrank
-- via map_comap_subtype (the map of the comap under p.subtype equals p ⊓ ker f)
-- and finrank_map_subtype_eq (injective subtype preserves finrank).
theorem inf_ker_restrict_bridge
    {K M : Type*} [Field K] [AddCommGroup M] [Module K M] [FiniteDimensional K M]
    (f : M →ₗ[K] M) (p : Submodule K M) (hf : ∀ x ∈ p, f x ∈ p) :
    Module.finrank K (p ⊓ LinearMap.ker f : Submodule K M)
      = Module.finrank K ↥(LinearMap.ker (f.restrict hf)) := by
  rw [LinearMap.ker_restrict hf]
  rw [← Submodule.map_comap_subtype p (LinearMap.ker f)]
  rw [Submodule.finrank_map_subtype_eq]

-- entry_kind: Builder
-- Split the combined `hd` disjunction into separate `hbot`/`hshift` premises
-- and apply `jordan_chain_ker_finrank`. The Finset.filter card from that
-- sibling lemma equals `Fintype.card {t // 0 < l t}` via `Fintype.card_subtype`.
theorem restrict_ker_finrank_count
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ M (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    Module.finrank K ↥(LinearMap.ker M) = Fintype.card {t : Fin p // 0 < l t} := by
  classical
  have hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0 := by
    intro t j hj
    rcases hd t j with ⟨_, h0⟩ | ⟨i, hi1, _⟩
    · exact h0
    · exact absurd hi1 (by omega)
  have hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩ := by
    intro t j hj
    rcases hd t j with ⟨h0, _⟩ | h
    · exact absurd h0 (by omega)
    · exact h
  have hcount := jordan_chain_ker_finrank M d hbot hshift
  rw [hcount, ← Fintype.card_subtype]

-- finrank(range N ⊓ ker N) = #{0 < l t} via a two-step transitive equality.
-- h_bridge: the W-side intersection range N ⊓ ker N is the image under the subtype
--   embedding of ker (N.restrict h_inv) (the kernel of N's restriction to range N),
--   so the two finranks agree — an abstract restriction↔intersection fact, no Jordan
--   structure needed.
-- h_count: ker (N.restrict h_inv) is spanned by the chain bottoms {d⟨t,0⟩ : 0 < l t},
--   an LI subfamily of the Jordan basis d, so its finrank is the bottom-count
--   #{0 < l t} (strong-hd: the j=0 constraint forces proper chains).
-- Eq.trans chains the two. Each sub-goal is local and abstract over (f,p) / (M,d).
theorem inf_ker_card
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩) :
    Module.finrank K (LinearMap.range N ⊓ LinearMap.ker N : Submodule K W)
      = Fintype.card {t : Fin p // 0 < l t}  := by
  have h_bridge := inf_ker_restrict_bridge N (LinearMap.range N) h_inv
  have h_count := restrict_ker_finrank_count (N.restrict h_inv) d hd
  exact h_bridge.trans h_count

-- Direct combinatorial count (leaf): card_sigma + card_fin reduce the LHS to a sum over the
-- sum-index, sum_sum_type splits it into the two summands `∑ (l t.1 + 1)` and `∑ 1 = m`.
-- sum_add_distrib peels the chain-length sum from the per-block `+1`; the `+1`s count the
-- nonzero-l blocks (= card subtype), and `sum_subtype`+`sum_subset` extend the subtype sum
-- of `l` to all of `Fin p` (the dropped `l t = 0` terms vanish), matching the RHS normal form.
theorem index_card_eq (p : ℕ) (l : Fin p → ℕ) (m : ℕ) :
    Fintype.card (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s))
        = (∑ t : Fin p, l t) + Fintype.card {t : Fin p // 0 < l t} + m  := by
  rw [Fintype.card_sigma]
  simp only [Fintype.card_fin]
  rw [Fintype.sum_sum_type]
  simp only [Sum.elim_inl, Sum.elim_inr, Finset.sum_const, smul_eq_mul, mul_one,
    Finset.card_univ, Fintype.card_fin]
  rw [Finset.sum_add_distrib]
  have h2 : (∑ _x : {t : Fin p // 0 < l t}, (1:ℕ)) = Fintype.card {t : Fin p // 0 < l t} := by
    simp [Finset.card_univ]
  have h1 : (∑ x : {t : Fin p // 0 < l t}, l ↑x) = ∑ t, l t := by
    rw [← Finset.sum_subtype (Finset.univ.filter (fun t => 0 < l t)) (fun x => by simp) l]
    apply Finset.sum_subset (Finset.filter_subset _ _)
    intro x _ hx
    simp only [Finset.mem_filter, Finset.mem_univ, true_and, not_lt, Nat.le_zero] at hx
    exact hx
  rw [h1, h2]

-- finrank W via rank-nullity over N: split finrank W = finrank(range N) + finrank(ker N),
-- then count each piece. h_rn (mathlib rank-nullity), h_range = ∑ l (basis d card, inline),
-- h_ker = finrank(range⊓ker) + m (disjoint-sup count on hC2/hC3, inline). Only genuine
-- sub-goal: inf_ker_card = #{0<l t} (strong-hd count, the j=0 constraint forces proper
-- chains so ker(N↾range) = span of chain bottoms). omega assembles the four ℕ equalities.
theorem finrank_eq
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (C : Submodule K W) (hC1 : C ≤ LinearMap.ker N)
    (hC2 : Disjoint C (LinearMap.range N))
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N)
    (m : ℕ) (cb : Module.Basis (Fin m) K C) :
    Module.finrank K W = (∑ t : Fin p, l t) + Fintype.card {t : Fin p // 0 < l t} + m  := by
  have h_rn : Module.finrank K (LinearMap.range N) + Module.finrank K (LinearMap.ker N)
      = Module.finrank K W :=
    LinearMap.finrank_range_add_finrank_ker N
  have h_range : Module.finrank K (LinearMap.range N) = ∑ t : Fin p, l t := by
    rw [Module.finrank_eq_card_basis d, Fintype.card_sigma]
    simp [Fintype.card_fin]
  have h_ker : Module.finrank K (LinearMap.ker N)
      = Module.finrank K (LinearMap.range N ⊓ LinearMap.ker N : Submodule K W) + m := by
    have hdisjoint : Disjoint C (LinearMap.range N ⊓ LinearMap.ker N) :=
      hC2.mono_right inf_le_left
    have hsup := Submodule.finrank_sup_add_finrank_inf_eq C
      (LinearMap.range N ⊓ LinearMap.ker N)
    have hbot : (C ⊓ (LinearMap.range N ⊓ LinearMap.ker N) : Submodule K W) = ⊥ :=
      disjoint_iff.mp hdisjoint
    have hm : Module.finrank K C = m := by
      rw [Module.finrank_eq_card_basis cb, Fintype.card_fin]
    rw [hbot, hC3, finrank_bot K W] at hsup
    omega
  have h_inf : Module.finrank K (LinearMap.range N ⊓ LinearMap.ker N : Submodule K W)
      = Fintype.card {t : Fin p // 0 < l t} := inf_ker_card N hN h_inv p l d hd
  omega

-- Count both sides against the common normal form `(∑ t, l t) + #{t // 0 < l t} + m`.
--   * `index_card_eq` : the index card reduces to it by pure Fin/Finset combinatorics
--     (card_sigma + card_sum + the zero-l terms drop out of the subtype sum).
--   * `finrank_eq` : `finrank W` reduces to it via rank-nullity over `range N` / `ker N`
--     (range-basis `d` gives `∑ l t`; the strong-`hd` count gives `#{0<l t}`; `C` gives `m`).
-- Both equal the same ℕ, so `h_card.trans h_finrank.symm` closes; finrank_eq carries the
-- strong `hd` (the `j=0` constraint), the weak-`hd` count having been disproved.
theorem family_card_strong
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (x : (Σ t : Fin p, Fin (l t)) → W)
    (hx : ∀ (t : Fin p) (j : Fin (l t)), N (x ⟨t, j⟩) = (↑(d ⟨t, j⟩) : W))
    (C : Submodule K W) (hC1 : C ≤ LinearMap.ker N)
    (hC2 : Disjoint C (LinearMap.range N))
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N)
    (m : ℕ) (cb : Module.Basis (Fin m) K C)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W))
    (hv_top : ∀ (t : {t : Fin p // 0 < l t}),
        v ⟨Sum.inl t, Fin.last (l t.1)⟩ = x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩)
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W)) :
    Fintype.card (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s))
        = Module.finrank K W  := by
  have h_card := index_card_eq p l m
  have h_finrank := finrank_eq N hN h_inv p l d hd C hC1 hC2 hC3 m cb
  exact h_card.trans h_finrank.symm

-- family_chain_strong: Jordan chain relation for each block with strong hd (j=0 on zero branch)
-- Identical structure to family_chain; the strong hd's extra conjunct is destructured and discarded.
-- entry_kind: Builder
theorem family_chain_strong
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (x : (Σ t : Fin p, Fin (l t)) → W)
    (hx : ∀ (t : Fin p) (j : Fin (l t)), N (x ⟨t, j⟩) = (↑(d ⟨t, j⟩) : W))
    (C : Submodule K W) (hC1 : C ≤ LinearMap.ker N)
    (hC2 : Disjoint C (LinearMap.range N))
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N)
    (m : ℕ) (cb : Module.Basis (Fin m) K C)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W))
    (hv_top : ∀ (t : {t : Fin p // 0 < l t}),
        v ⟨Sum.inl t, Fin.last (l t.1)⟩ = x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩)
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W)) :
    ∀ (s : ({t : Fin p // 0 < l t} ⊕ Fin m))
      (j : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)),
        N (v ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (v ⟨s, j⟩) = v ⟨s, i⟩ := by
  intro s j
  rcases s with ⟨t, ht⟩ | c
  · -- Sum.inl ⟨t, ht⟩: chain block, t : Fin p, ht : 0 < l t, j : Fin (l t + 1)
    induction j using Fin.lastCases with
    | last =>
      -- j = Fin.last (l t): top element, N maps it to d ⟨t, l t - 1⟩ via hx
      right
      refine ⟨(⟨l t - 1, by omega⟩ : Fin (l t)).castSucc, ?_, ?_⟩
      · simp [Fin.val_last]; omega
      · rw [hv_top ⟨t, ht⟩, hx t ⟨l t - 1, by omega⟩,
            ← hv_chain ⟨t, ht⟩ ⟨l t - 1, Nat.sub_lt ht Nat.one_pos⟩]
    | cast i =>
      -- j = i.castSucc: inner chain element, use hd t i (strong form)
      rw [hv_chain ⟨t, ht⟩ i]
      rcases hd t i with ⟨_, h0⟩ | ⟨i', hi'_eq, hi'_val⟩
      · left
        simp only [LinearMap.restrict_apply] at h0
        exact congr_arg Subtype.val h0
      · right
        have hval : N (↑(d ⟨t, i⟩) : W) = ↑(d ⟨t, i'⟩) := by
          simp only [LinearMap.restrict_apply] at hi'_val
          exact congr_arg Subtype.val hi'_val
        refine ⟨i'.castSucc, ?_, ?_⟩
        · simp only [Fin.val_castSucc]; omega
        · rw [hval, ← hv_chain ⟨t, ht⟩ i']
  · -- Sum.inr c: complement basis, block of length 1
    simp only [Sum.elim_inr]
    left
    have hj : j = (0 : Fin 1) := Fin.eq_zero j
    subst hj
    rw [hv_C c]
    exact LinearMap.mem_ker.mp (hC1 (Submodule.coe_mem (cb c)))

-- LinearIndependent v via `Fintype.linearIndependent_iff`: split a vanishing combination
-- `∑ g i • v i = 0` into two phases (combinator is trivial; both phases subsume all parent hyps).
--   * `above_bottom_vanish` : applying N to the relation sends chain tops/interiors to the
--     range-basis `d` (bottoms/complement to 0), so `d`-LI forces every above-bottom coeff
--     `g ⟨inl t, j⟩` (j ≥ 1) to vanish. Strictly simpler: only a partial coeff result.
--   * `bottom_complement_coeffs` : given the above-bottom coeffs are 0, the residual relation
--     lives among chain bottoms `d⟨t,0⟩ ∈ range N ⊓ ker N` and complement `cb c ∈ C`; `hC2`
--     disjointness + `chain_bottoms_li` + `cb`-LI kill the rest. Strictly simpler: extra `habove`.
theorem family_li_strong

    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (x : (Σ t : Fin p, Fin (l t)) → W)
    (hx : ∀ (t : Fin p) (j : Fin (l t)), N (x ⟨t, j⟩) = (↑(d ⟨t, j⟩) : W))
    (C : Submodule K W) (hC1 : C ≤ LinearMap.ker N)
    (hC2 : Disjoint C (LinearMap.range N))
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N)
    (m : ℕ) (cb : Module.Basis (Fin m) K C)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W))
    (hv_top : ∀ (t : {t : Fin p // 0 < l t}),
        v ⟨Sum.inl t, Fin.last (l t.1)⟩ = x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩)
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W)) :
    LinearIndependent K v  := by
  classical
  rw [Fintype.linearIndependent_iff]
  intro g hg
  have habove := above_bottom_vanish N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg
  exact bottom_complement_coeffs N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove

-- Decompose `LinearIndependent v ∧ ⊤ ≤ span v` via the count-bridge: prove the LI
-- conjunct directly plus the dimension count `card index = finrank W`, then derive the
-- span conjunct from mathlib's `LinearIndependent.span_eq_top_of_card_eq_finrank'`.
--   * `family_li_strong` : `LinearIndependent K v` — chain/complement family is LI (apply N
--     once: chain tops/interiors land on the range-basis `d`, bottoms/complement on ker).
--   * `family_card_strong` : `card index = finrank K W` — the crux that STRONG `hd` (the
--     `j = 0` constraint on the `= 0` branch) unlocks: it forces `ker N.restrict = span of
--     chain bottoms`, so rank-nullity closes the count (the weak-`hd` count was disproved).
-- Both subsume the parent's hypotheses; the combinator needs only `[FiniteDimensional K W]`.
theorem family_li_span_strong
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (x : (Σ t : Fin p, Fin (l t)) → W)
    (hx : ∀ (t : Fin p) (j : Fin (l t)), N (x ⟨t, j⟩) = (↑(d ⟨t, j⟩) : W))
    (C : Submodule K W) (hC1 : C ≤ LinearMap.ker N)
    (hC2 : Disjoint C (LinearMap.range N))
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N)
    (m : ℕ) (cb : Module.Basis (Fin m) K C)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W))
    (hv_top : ∀ (t : {t : Fin p // 0 < l t}),
        v ⟨Sum.inl t, Fin.last (l t.1)⟩ = x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩)
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W)) :
    LinearIndependent K v ∧
      (⊤ : Submodule K W) ≤ Submodule.span K (Set.range v)  := by
  have h_li : LinearIndependent K v :=
    family_li_strong N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v hv_chain hv_top hv_C
  have h_card : Fintype.card (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
        Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s))
      = Module.finrank K W :=
    family_card_strong N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v hv_chain hv_top hv_C
  exact ⟨h_li, (h_li.span_eq_top_of_card_eq_finrank' h_card).ge⟩

-- Build the extended chain family `v` over the index `P ⊕ Fin m` (`P := {t // 0 < l t}`,
-- `m := finrank K C`, `cb := finBasis K C`): each nonempty range-`N` chain `t` is `Fin.snoc`-
-- extended by its top preimage `x ⟨t, l t - 1⟩`, each complement vector `cb c` is a length-1
-- chain. The three defining equations hold by `Fin.snoc_castSucc`/`Fin.snoc_last`/`rfl`.
-- Two sub-goals consume them, then a pure `Fintype.equivFin` relabel discharges the existential:
--   * `family_li_span_strong` (Backward): `LinearIndependent ∧ ⊤ ≤ span` — STRONG `hd` (the
--     `j = 0` constraint on the `= 0` branch) is what makes the dimension count close; this is
--     the crux the weak-`hd` `family_li_span` could not prove (it was disproved).
--   * `family_chain_strong` (Builder): the within-block Jordan chain relation; weak `hd` suffices,
--     so it aliases the proved `family_chain` after dropping the `j = 0` conjunct.
-- Both are re-declared as own sub-goals (cross-strategy citations are not auto-imported).
theorem extended_jordan_family_strong
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (x : (Σ t : Fin p, Fin (l t)) → W)
    (hx : ∀ (t : Fin p) (j : Fin (l t)), N (x ⟨t, j⟩) = (↑(d ⟨t, j⟩) : W))
    (C : Submodule K W) (hC1 : C ≤ LinearMap.ker N)
    (hC2 : Disjoint C (LinearMap.range N))
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N) :
    ∃ (r : ℕ) (k : Fin r → ℕ) (v : (Σ s : Fin r, Fin (k s)) → W),
      LinearIndependent K v ∧
      (⊤ : Submodule K W) ≤ Submodule.span K (Set.range v) ∧
      ∀ (s : Fin r) (j : Fin (k s)),
        N (v ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (v ⟨s, j⟩) = v ⟨s, i⟩  := by
  classical
  let m := Module.finrank K C
  let cb : Module.Basis (Fin m) K C := Module.finBasis K C
  let P := {t : Fin p // 0 < l t}
  let kk : (P ⊕ Fin m) → ℕ := Sum.elim (fun t : P => l t.1 + 1) (fun _ : Fin m => 1)
  let v : (Σ s : (P ⊕ Fin m), Fin (kk s)) → W := fun sj =>
    match sj with
    | ⟨Sum.inl t, j⟩ =>
        Fin.snoc (α := fun _ => W) (fun i => (↑(d ⟨t.1, i⟩) : W))
          (x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩) j
    | ⟨Sum.inr c, _⟩ => (cb c : W)
  have hv_chain : ∀ (t : P) (i : Fin (l t.1)),
      v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W) :=
    fun t i => Fin.snoc_castSucc _ _ i
  have hv_top : ∀ (t : P),
      v ⟨Sum.inl t, Fin.last (l t.1)⟩ = x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩ :=
    fun t => Fin.snoc_last _ _
  have hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W) := fun _ => rfl
  obtain ⟨hLI, hspan⟩ :=
    family_li_span_strong N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v hv_chain hv_top hv_C
  have hchain :=
    family_chain_strong N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v hv_chain hv_top hv_C
  set e := Fintype.equivFin (P ⊕ Fin m) with he
  set φ := Equiv.sigmaCongrLeft' (β := fun a : (P ⊕ Fin m) => Fin (kk a)) e with hφ
  refine ⟨Fintype.card (P ⊕ Fin m), fun s => kk (e.symm s), fun q => v (φ.symm q), ?_, ?_, ?_⟩
  · exact hLI.comp _ φ.symm.injective
  · have hr : Set.range (fun q => v (φ.symm q)) = Set.range v := by
      rw [show (fun q => v (φ.symm q)) = v ∘ φ.symm from rfl, Set.range_comp,
        Equiv.range_eq_univ, Set.image_univ]
    rw [hr]; exact hspan
  · intro s j
    exact hchain (e.symm s) j

-- Package the LI + spanning chain family `v` from `h` into a `Module.Basis` via
-- `Module.Basis.mk hLI hsp`, then transport the chain property: `Module.Basis.mk_apply`
-- rewrites every `c ⟨s,_⟩` back to `v ⟨s,_⟩`, so the goal is literally `hchain s j`.
theorem family_to_basis
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (h : ∃ (r : ℕ) (k : Fin r → ℕ) (v : (Σ s : Fin r, Fin (k s)) → W),
      LinearIndependent K v ∧
      (⊤ : Submodule K W) ≤ Submodule.span K (Set.range v) ∧
      ∀ (s : Fin r) (j : Fin (k s)),
        N (v ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (v ⟨s, j⟩) = v ⟨s, i⟩) :
    ∃ (r : ℕ) (k : Fin r → ℕ)
      (c : Module.Basis (Σ s : Fin r, Fin (k s)) K W),
      ∀ (s : Fin r) (j : Fin (k s)),
        N (c ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (c ⟨s, j⟩) = c ⟨s, i⟩  := by
  obtain ⟨r, k, v, hLI, hsp, hchain⟩ := h
  refine ⟨r, k, Module.Basis.mk hLI hsp, ?_⟩
  intro s j
  simp only [Module.Basis.mk_apply]
  exact hchain s j

-- ker_range_complement_2: Submodule.exists_isCompl (field → complementedLattice) finds C ≤ ker N
-- disjoint from range N, supplementing range N ⊓ ker N to all of ker N.
-- entry_kind: Builder
theorem ker_range_complement_2
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        (N.restrict h_inv) (d ⟨t, j⟩) = 0 ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩) :
    ∃ C : Submodule K W,
      C ≤ LinearMap.ker N ∧ Disjoint C (LinearMap.range N) ∧
        C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N := by
  -- Find a complement of (range N ⊓ ker N) inside ker N (possible over a field).
  let S := (LinearMap.range N ⊓ LinearMap.ker N).comap (LinearMap.ker N).subtype
  obtain ⟨C₀, hC₀⟩ := Submodule.exists_isCompl S
  refine ⟨C₀.map (LinearMap.ker N).subtype, ?_, ?_, ?_⟩
  · -- C ≤ ker N: every image under ker N inclusion lies in ker N
    rintro x ⟨y, -, rfl⟩
    exact SetLike.coe_mem y
  · -- Disjoint C (range N)
    rw [Submodule.disjoint_def]
    intro x hxC hxR
    have hxKer : x ∈ LinearMap.ker N := by
      obtain ⟨y, -, rfl⟩ := hxC; exact SetLike.coe_mem y
    obtain ⟨y, hyC₀, rfl⟩ := hxC
    have hyS : y ∈ S := Submodule.mem_comap.mpr (Submodule.mem_inf.mpr ⟨hxR, hxKer⟩)
    have hbot : y ∈ S ⊓ C₀ := Submodule.mem_inf.mpr ⟨hyS, hyC₀⟩
    have hy0 : y = 0 := by
      have h : S ⊓ C₀ = ⊥ := hC₀.disjoint.eq_bot
      simp only [h, Submodule.mem_bot] at hbot; exact hbot
    simp [hy0]
  · -- C ⊔ (range N ⊓ ker N) = ker N
    ext x
    simp only [Submodule.mem_sup, Submodule.mem_map, Submodule.mem_inf]
    constructor
    · rintro ⟨a, ⟨ya, -, rfl⟩, b, ⟨-, hbK⟩, rfl⟩
      exact (LinearMap.ker N).add_mem (SetLike.coe_mem ya) hbK
    · intro hxK
      let x' : ↥(LinearMap.ker N) := ⟨x, hxK⟩
      have hx'top : x' ∈ S ⊔ C₀ := hC₀.sup_eq_top ▸ Submodule.mem_top
      obtain ⟨s, hs, c, hc, hsc⟩ := Submodule.mem_sup.mp hx'top
      have hs_inf : (s : W) ∈ LinearMap.range N ⊓ LinearMap.ker N :=
        Submodule.mem_comap.mp hs
      have heq : (s : W) + (c : W) = x := by
        have h : ((s + c : ↥(LinearMap.ker N)) : W) = x := congr_arg Subtype.val hsc
        simpa using h
      exact ⟨c.1, ⟨c, hc, rfl⟩, s.1, hs_inf, (add_comm (c : W) (s : W)).trans heq⟩

-- entry_kind: Builder
-- block_top_preimages_2: each range-basis element has a preimage under N;
-- pick via LinearMap.mem_range on the subtype membership (d tj).2
theorem block_top_preimages_2
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        (N.restrict h_inv) (d ⟨t, j⟩) = 0 ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩) :
    ∃ x : (Σ t : Fin p, Fin (l t)) → W,
      ∀ (t : Fin p) (j : Fin (l t)), N (x ⟨t, j⟩) = (↑(d ⟨t, j⟩) : W) := by
  refine ⟨fun tj => (LinearMap.mem_range.mp (d tj).2).choose, ?_⟩
  intro t j
  exact (LinearMap.mem_range.mp (d ⟨t, j⟩).2).choose_spec

-- Assemble the strong block Jordan basis of `W` from the strong chain basis `d` of `range N`.
-- Discharge the two existential constructions via PROVED siblings, then run the LA glue:
--   * `block_top_preimages_2` (proved): lift each chain element through `N` → `x`, `hx`.
--   * `ker_range_complement_2` (proved): split `ker N` as `C ⊕ (range N ⊓ ker N)` → `C`, `hC*`.
--   * `extended_jordan_family_strong`: build the extended chain family `v` and prove
--     `LinearIndependent ∧ ⊤ ≤ span` (STRONG `hd` makes the dimension count close) + chain.
--   * `family_to_basis`: package an LI/spanning chain family into a `Module.Basis`,
--     transporting the chain property (generic, reusable; no `N`-structure reasoning).
-- The two preimage/complement siblings need only the WEAK `hd`, derived by dropping the
-- `j = 0` constraint from the strong left branch.
theorem assemble_block_jordan_strong
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩) :
    ∃ (r : ℕ) (k : Fin r → ℕ)
      (c : Module.Basis (Σ s : Fin r, Fin (k s)) K W),
      ∀ (s : Fin r) (j : Fin (k s)),
        N (c ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (c ⟨s, j⟩) = c ⟨s, i⟩  := by
  have hd_weak : ∀ (t : Fin p) (j : Fin (l t)),
      (N.restrict h_inv) (d ⟨t, j⟩) = 0 ∨
        ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
          (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩ :=
    fun t j => (hd t j).imp (fun h => h.2) id
  obtain ⟨x, hx⟩ := block_top_preimages_2 N hN h_inv p l d hd_weak
  obtain ⟨C, hC1, hC2, hC3⟩ := ker_range_complement_2 N hN h_inv p l d hd_weak
  have hfam := extended_jordan_family_strong N hN h_inv p l d hd x hx C hC1 hC2 hC3
  exact family_to_basis N hfam

end Library.LinearAlgebra.JordanForm.FamilyConstruction
