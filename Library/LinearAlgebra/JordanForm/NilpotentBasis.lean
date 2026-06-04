import Library.LinearAlgebra.JordanForm.BlockEnum
import Library.LinearAlgebra.JordanForm.Defs
import Library.LinearAlgebra.JordanForm.RangeBlock
import Mathlib

open Library.LinearAlgebra.JordanForm.BlockEnum
open Library.LinearAlgebra.JordanForm.Defs
open Library.LinearAlgebra.JordanForm.RangeBlock

namespace Library.LinearAlgebra.JordanForm.NilpotentBasis

-- jordan_chain_basis_matrix_form: chain-basis structure for nilpotent N implies IsJordanForm
-- and zero diagonal, by reading column structure via LinearMap.toMatrix_apply.
theorem jordan_chain_basis_matrix_form
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (b : Module.Basis (Fin (Module.finrank K W)) K W)
    (hb : ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i) :
    IsJordanForm (LinearMap.toMatrix b b N) ∧
      ∀ i : Fin (Module.finrank K W), (LinearMap.toMatrix b b N) i i = 0 := by
  have mij : ∀ (i j : Fin (Module.finrank K W)),
      (LinearMap.toMatrix b b N) i j = b.repr (N (b j)) i :=
    fun i j => LinearMap.toMatrix_apply b b N i j
  -- when N(b j) = b k, entry (i,j) = if k = i then 1 else 0
  have col_basis : ∀ (i j k : Fin (Module.finrank K W)),
      N (b j) = b k → (LinearMap.toMatrix b b N) i j = if k = i then 1 else 0 := by
    intro i j k h; rw [mij, h, Module.Basis.repr_self_apply]
  -- diagonal is zero: N(b i) = 0 or N(b i) = b k with (k:ℕ)+1 = (i:ℕ), so k ≠ i
  have diag_zero : ∀ i : Fin (Module.finrank K W),
      (LinearMap.toMatrix b b N) i i = 0 := by
    intro i
    rcases hb i with h | ⟨k, hki, hNi⟩
    · simp [mij, h]
    · rw [col_basis i i k hNi, if_neg]
      exact fun heq => absurd hki (by rw [congrArg Fin.val heq]; omega)
  refine ⟨fun i j => ?_, diag_zero⟩
  show (if (i : ℕ) = (j : ℕ) then True
        else if (i : ℕ) + 1 = (j : ℕ) then
          (LinearMap.toMatrix b b N) i j = 0 ∨
            ((LinearMap.toMatrix b b N) i j = 1 ∧
              (LinearMap.toMatrix b b N) i i = (LinearMap.toMatrix b b N) j j)
        else (LinearMap.toMatrix b b N) i j = 0)
  rcases hb j with h | ⟨k, hkj, hNj⟩
  · -- N(b j) = 0: entry (i,j) = 0 in all positions
    have hij0 : (LinearMap.toMatrix b b N) i j = 0 := by simp [mij, h]
    split_ifs <;> simp [hij0]
  · -- N(b j) = b k: entry (i,j) = if k = i then 1 else 0
    rw [col_basis i j k hNj]
    by_cases hki : k = i
    · -- k = i: entry is 1; hkj says k+1=j, so after subst i replaced by k
      subst hki
      simp only [if_true]
      -- goal: if ↑k=↑j then True else if ↑k+1=↑j then 1=0∨True∧Mkk=Mjj else 1=0
      rw [if_neg (show ¬ (k : ℕ) = (j : ℕ) from by omega), if_pos hkj]
      -- goal: 1 = 0 ∨ True ∧ M k k = M j j
      exact Or.inr ⟨trivial, by simp [diag_zero]⟩
    · -- k ≠ i: entry is 0
      simp only [if_neg hki]
      split_ifs <;> simp

-- Reindex via block_enum_consecutive + cardinality bridge.
-- block_enum_consecutive (proved brick s10915) gives e : Fin (∑ k s) ≃ Σ s, Fin (k s).
-- finrank K W = ∑ k s from basis c; finCongr then closes Fin (finrank W) ≃ Fin (∑ k s).
-- Compose: φ := finCongr.trans e gives Fin (finrank W) ≃ Σ s, Fin (k s); reindex c via φ.
theorem block_basis_to_consecutive
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (r : ℕ) (k : Fin r → ℕ)
    (c : Module.Basis (Σ s : Fin r, Fin (k s)) K W)
    (hc : ∀ (s : Fin r) (j : Fin (k s)),
        N (c ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (c ⟨s, j⟩) = c ⟨s, i⟩) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i  := by
  obtain ⟨e, he⟩ := block_enum_consecutive k
  have h_card : Module.finrank K W = ∑ s, k s := by
    rw [Module.finrank_eq_card_basis c, Fintype.card_sigma]
    simp [Fintype.card_fin]
  let φ : Fin (Module.finrank K W) ≃ Σ s : Fin r, Fin (k s) :=
    (finCongr h_card).trans e
  refine ⟨c.reindex φ.symm, ?_⟩
  intro j
  have hbj : (c.reindex φ.symm) j = c (φ j) := by
    simp [Module.Basis.reindex_apply]
  rcases hc (φ j).1 (φ j).2 with h0 | ⟨i, hi_eq, hi_N⟩
  · left
    rw [hbj]
    have heq : (⟨(φ j).1, (φ j).2⟩ : Σ s : Fin r, Fin (k s)) = φ j := rfl
    rw [heq] at h0
    exact h0
  · right
    refine ⟨φ.symm ⟨(φ j).1, i⟩, ?_, ?_⟩
    · set p := φ.symm ⟨(φ j).1, i⟩ with hp
      have hφp : φ p = ⟨(φ j).1, i⟩ := by simp [hp]
      have h_fst : (φ p).1 = (φ j).1 := by rw [hφp]
      have h_snd_p : ((φ p).2 : ℕ) = (i : ℕ) := by rw [hφp]
      have hep : φ p = e ((finCongr h_card) p) := rfl
      have hej : φ j = e ((finCongr h_card) j) := rfl
      have h_fst' : (e ((finCongr h_card) p)).1 = (e ((finCongr h_card) j)).1 := by
        rw [← hep, ← hej]; exact h_fst
      have hiff := he ((finCongr h_card) p) ((finCongr h_card) j) h_fst'
      have h_lhs : ((e ((finCongr h_card) p)).2 : ℕ) + 1 = ((e ((finCongr h_card) j)).2 : ℕ) := by
        rw [← hep, ← hej]
        rw [h_snd_p]; exact hi_eq
      have h_pj : ((finCongr h_card) p : ℕ) + 1 = ((finCongr h_card) j : ℕ) := hiff.mp h_lhs
      simpa using h_pj
    · rw [hbj]
      have hbp : (c.reindex φ.symm) (φ.symm ⟨(φ j).1, i⟩) = c ⟨(φ j).1, i⟩ := by
        rw [Module.Basis.reindex_apply]; simp
      rw [hbp]
      have heq : (⟨(φ j).1, (φ j).2⟩ : Σ s : Fin r, Fin (k s)) = φ j := rfl
      rw [heq] at hi_N
      exact hi_N

-- Glue `bU` (Jordan basis of `range N`) up to a Jordan basis of `W` in two stages,
-- separating the linear-algebra content from the index layout that sank prior attempts.
--   * `block_jordan_basis_exists` (LA chain-glue): lift chain tops through `N`, extend
--     `ker N`, assemble a Jordan basis of `W` indexed by genuine `Σ s : Fin r, Fin (k s)`
--     blocks — each `Fin (k s)` is a chain and `N` strictly decrements the within-block
--     index. Simpler than the parent: it carries no `Fin (finrank W)`-consecutiveness
--     constraint, so the painful index layout is out of the way. The block form makes
--     π-cycles and `some`-collisions (which made the predecessor form of dead `s10921`
--     insufficient) impossible by construction.
--   * `block_basis_to_consecutive` (index layout): reindex any block-form Jordan basis to
--     the `Fin (finrank W)` consecutive form, reusing the proved `block_enum_consecutive`
--     brick. Simpler than the parent: pure index bookkeeping over a basis already given.
-- Combine: `obtain` the block basis, then `exact` the reindexed consecutive basis.
theorem succ_glue
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) (hN0 : N ≠ 0)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (bU : Module.Basis (Fin (Module.finrank K (LinearMap.range N))) K (LinearMap.range N))
    (hbU : ∀ j : Fin (Module.finrank K (LinearMap.range N)),
        (N.restrict h_inv) (bU j) = 0 ∨
          ∃ i : Fin (Module.finrank K (LinearMap.range N)),
            (i : ℕ) + 1 = (j : ℕ) ∧ (N.restrict h_inv) (bU j) = bU i) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i  := by
  obtain ⟨r, k, c, hc⟩ := block_jordan_basis_exists N hN hN0 h_inv bU hbU
  exact block_basis_to_consecutive N r k c hc

-- Strong induction on the dimension bound `n`, kept INLINE (lesson: extracting the
-- succ-step with a `∀ {W'} ih` hypothesis binds a fresh universe `u_3 ≠ u_2`, making `ih`
-- unusable on `↥(range N)`; here the inline `ih` lives in `W`'s universe and applies).
-- Base `n=0`: `Fin (finrank W)` is empty, the claim is vacuous. Succ: if `N = 0` every
-- vector is killed (left disjunct); else descend to `U := range N` — `range_finrank_le`
-- gives `finrank U ≤ m`, `range_restrict_nilpotent` its nilpotency, so `ih` yields a Jordan
-- chain basis of `U`, and `succ_glue` extends/glues it to a basis of `W`.
theorem jordan_chain_basis_dim_induction
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) (n : ℕ) (hdim : Module.finrank K W ≤ n) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i  := by
  induction n generalizing W N hN with
  | zero => exact ⟨Module.finBasis K W, fun j => absurd j.isLt (by omega)⟩
  | succ m ih =>
      by_cases hN0 : N = 0
      · subst hN0
        exact ⟨Module.finBasis K W, fun j => Or.inl rfl⟩
      · have h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N :=
          fun x _ => LinearMap.mem_range_self N x
        have hN' : IsNilpotent (N.restrict h_inv) := range_restrict_nilpotent N hN h_inv
        have hle : Module.finrank K (LinearMap.range N) ≤ m := range_finrank_le N hN hN0 hdim
        obtain ⟨bU, hbU⟩ := ih (N.restrict h_inv) hN' hle
        exact succ_glue N hN hN0 h_inv bU hbU

-- Reduce to a strong-induction-ready generalized lemma: the same statement for an
-- arbitrary nilpotent operator on a space of dimension ≤ n (the bound `n` is the
-- well-founded measure for induction on `Module.finrank`, which cannot be run with the
-- ambient `W` fixed). The parent is the `n := finrank K W` instance.
-- The generalized lemma carries the textbook recursion (N = 0 base; `range N` descent).
theorem jordan_chain_basis_exists
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i  := by
  have h_chain := jordan_chain_basis_dim_induction N hN
  exact h_chain (Module.finrank K W) le_rfl

-- Split into (1) existence of a "Jordan-chain" basis structure for the nilpotent N,
-- and (2) a matrix-translation lemma converting that structure to IsJordanForm + diag=0.
-- Sub-goal 1 is the hard linear-algebra existence (kernel-filtration / chain construction)
-- expressed structurally without any matrix vocabulary — strictly simpler than the parent.
-- Sub-goal 2 is a pure matrix-level computation given the structural hypothesis: each
-- column of toMatrix b b N is either zero or a standard basis vector e_{j-1}, which
-- immediately yields the IsJordanForm shape and zero diagonal.
theorem nilpotent_has_jordan_basis
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      IsJordanForm (LinearMap.toMatrix b b N) ∧
    ∀ i : Fin (Module.finrank K W), (LinearMap.toMatrix b b N) i i = 0  := by
  have h_exists := jordan_chain_basis_exists N hN
  obtain ⟨b, hb⟩ := h_exists
  have h_matrix := jordan_chain_basis_matrix_form N hN b hb
  exact ⟨b, h_matrix.1, h_matrix.2⟩

end Library.LinearAlgebra.JordanForm.NilpotentBasis
