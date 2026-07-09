import Library.LinearAlgebra.JordanForm.ChainKernel
import Library.LinearAlgebra.JordanForm.FamilyCoeffs
import Mathlib

open Library.LinearAlgebra.JordanForm.ChainKernel
open Library.LinearAlgebra.JordanForm.FamilyCoeffs

/-!
# Jordan Normal Form — Family Construction

This file assembles a Jordan basis for a nilpotent endomorphism `N` on a finite-dimensional
`K`-module `W`.  Starting from a chain basis `d` of `range N` (with strong chain data `hd`)
and a complementary submodule `C ≤ ker N`, it constructs an extended chain family `v`
(one `Fin.snoc`-augmented chain per nonempty block, one length-1 chain per complement vector),
proves it is linearly independent and spanning, and packages the result as a `Module.Basis`
satisfying the Jordan chain relation.  The key cardinality count — `finrank K W = ∑ l t + #{t // 0 < l t} + m` — requires the **strong** form of `hd` (the `j = 0` constraint on the zero
branch), which forces `ker (N.restrict) = span` of the chain bottoms.
-/

namespace Library.LinearAlgebra.JordanForm.FamilyConstruction

/-- The finrank of `p ⊓ ker f` in `M` equals the finrank of the kernel of the restriction
`f.restrict hf`, via the identification `Submodule.map_comap_subtype` and the fact that the
injective subtype embedding preserves finrank. -/
theorem inf_ker_restrict_bridge
    {K M : Type*} [Field K] [AddCommGroup M] [Module K M] [FiniteDimensional K M]
    (f : M →ₗ[K] M) (p : Submodule K M) (hf : ∀ x ∈ p, f x ∈ p) :
    Module.finrank K (p ⊓ LinearMap.ker f : Submodule K M)
      = Module.finrank K ↥(LinearMap.ker (f.restrict hf)) := by
  rw [LinearMap.ker_restrict hf]
  rw [← Submodule.map_comap_subtype p (LinearMap.ker f)]
  rw [Submodule.finrank_map_subtype_eq]

/-- Given a Jordan chain basis `d` for `R` whose chain data `hd` combines the zero and shift
branches in one disjunction, the finrank of `ker M` equals the number of nonempty chains
`Fintype.card {t : Fin p // 0 < l t}`.  The proof splits `hd` into separate `hbot`/`hshift`
hypotheses and applies `jordan_chain_ker_finrank`. -/
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

variable {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]

/-- The finrank of `range N ⊓ ker N` equals `Fintype.card {t : Fin p // 0 < l t}`.
The proof chains `inf_ker_restrict_bridge` (which identifies the `W`-side intersection with
the kernel of the restricted map) and `restrict_ker_finrank_count` (which counts the kernel
of the restricted map against the chain bottoms using the strong chain data `hd`). -/
theorem inf_ker_card
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

/-- A pure combinatorial identity: the cardinality of the extended index type
`Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m), Fin (Sum.elim (fun t => l t.1 + 1) (fun _ => 1) s)`
equals `(∑ t : Fin p, l t) + Fintype.card {t : Fin p // 0 < l t} + m`.
Proved by `card_sigma`, `sum_sum_type`, and extending the nonempty-block sum of `l` to all
of `Fin p` (the zero-length terms vanish). -/
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

/-- The finrank of `W` equals `(∑ t : Fin p, l t) + Fintype.card {t : Fin p // 0 < l t} + m`.
The proof applies rank-nullity to split `finrank W = finrank (range N) + finrank (ker N)`,
counts `finrank (range N) = ∑ l t` from the basis `d`, decomposes `ker N = C ⊕ (range N ⊓ ker N)`
using the disjointness hypotheses to get `finrank (ker N) = #{0 < l t} + m`, and assembles
by `omega`. -/
theorem finrank_eq
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

/-- The cardinality of the extended index type equals `Module.finrank K W`.
This is the dimension-count bridge used to promote linear independence to a basis: it combines
`index_card_eq` (a pure combinatorial reduction) with `finrank_eq` (rank-nullity over `N`)
via transitivity, requiring the strong form of `hd`. -/
theorem family_card_strong
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

/-- The extended chain family `v` satisfies the Jordan chain relation: for each block index `s`
and position `j`, either `N (v ⟨s, j⟩) = 0` or there exists an immediate predecessor `i` with
`N (v ⟨s, j⟩) = v ⟨s, i⟩`.  For `Sum.inl` blocks the proof uses `Fin.lastCases` on `j`,
delegating the top element to `hx` and inner elements to the strong chain data `hd`; for
`Sum.inr` complement elements the result follows from `hC1`. -/
theorem family_chain_strong
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

/-- The extended chain family `v` is linearly independent over `K`.
The proof uses `Fintype.linearIndependent_iff`: given a vanishing linear combination `∑ g i • v i = 0`,
`above_bottom_vanish` (applying `N` once) forces all above-bottom coefficients to zero, and
then `bottom_complement_coeffs` kills the remaining bottom-chain and complement coefficients
using disjointness of `C` and `range N`. -/
theorem family_li_strong

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

/-- The extended chain family `v` is linearly independent and its span is all of `W`.
Linear independence comes from `family_li_strong`; the spanning property is deduced from
`family_card_strong` (which requires the strong form of `hd`) via
`LinearIndependent.span_eq_top_of_card_eq_finrank'`. -/
theorem family_li_span_strong
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

/-- Given a strong Jordan chain basis `d` of `range N` with strong data `hd`, preimages `x`
under `N`, and a complement `C` of `range N ⊓ ker N` in `ker N`, this constructs an explicit
extended chain family `v` over `{t // 0 < l t} ⊕ Fin m` (each nonempty block extended by its
top preimage via `Fin.snoc`, each complement vector a length-1 block), proves `LinearIndependent K v`,
`⊤ ≤ span K (range v)`, and the Jordan chain relation, then relabels the index by `Fintype.equivFin`
to produce the existential in standard form. -/
theorem extended_jordan_family_strong
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

/-- Given a linearly independent, spanning chain family `v` (as produced by
`extended_jordan_family_strong`), constructs a `Module.Basis` `c` with the same index type
and verifies that `c` satisfies the Jordan chain relation.  The basis is built by `Module.Basis.mk`,
and the chain property is transferred using `Module.Basis.mk_apply`. -/
theorem family_to_basis
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

/-- Over a field `K`, the intersection `range N ⊓ ker N` has a complement `C` inside `ker N`
with `C ≤ ker N`, `Disjoint C (range N)`, and `C ⊔ (range N ⊓ ker N) = ker N`.
The complement is obtained by applying `Submodule.exists_isCompl` to the coimage of
`range N ⊓ ker N` under the inclusion of `ker N`, using that submodules over a field form
a complemented lattice. -/
theorem ker_range_complement_2
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

/-- For each basis element `d ⟨t, j⟩` of `range N`, produces a preimage `x ⟨t, j⟩` in `W`
satisfying `N (x ⟨t, j⟩) = ↑(d ⟨t, j⟩)`, using the fact that every element of `range N`
has a preimage under `N`. -/
theorem block_top_preimages_2
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

/-- The main assembly theorem: given a nilpotent endomorphism `N` on `W` with a strong Jordan
chain basis `d` of `range N`, produces a `Module.Basis` `c` of `W` indexed by `Σ s : Fin r, Fin (k s)`
such that `c` satisfies the Jordan chain relation at every position.  The proof derives the weak
form of `hd` to run `block_top_preimages_2` and `ker_range_complement_2`, then applies
`extended_jordan_family_strong` with the strong `hd` to close the dimension count, and finally
packages the result via `family_to_basis`. -/
theorem assemble_block_jordan_strong
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
