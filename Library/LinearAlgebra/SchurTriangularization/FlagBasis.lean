import Mathlib

namespace Library.LinearAlgebra.SchurTriangularization.FlagBasis

-- flag_span_iic_zero: base case j=0 of span-equals-flag using Set.Iic singleton + bot_sup_eq
-- entry_kind: Builder
theorem flag_span_iic_zero :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V)
      (v : Fin (Module.finrank K V) → V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ n, n < Module.finrank K V →
        ∃ vnext, vnext ∈ W (n + 1) ∧
          W n ⊔ Submodule.span K {vnext} = W (n + 1)) →
      (∀ j : Fin (Module.finrank K V),
        W j.val ⊔ Submodule.span K {v j} = W (j.val + 1)) →
      ∀ (h : 0 < Module.finrank K V),
        Submodule.span K (v '' Set.Iic (⟨0, h⟩ : Fin (Module.finrank K V))) = W 1 := by
  intro K _ V _ _ _ W v hW0 _ _ _ hchain h
  have hIic : Set.Iic (⟨0, h⟩ : Fin (Module.finrank K V)) = {⟨0, h⟩} := by
    ext j; simp [Set.mem_Iic, Set.mem_singleton_iff, Fin.ext_iff, Fin.le_def]
  rw [hIic, Set.image_singleton]
  have hstep := hchain ⟨0, h⟩
  simp only [Nat.zero_add] at hstep
  rw [hW0] at hstep
  simp only [bot_sup_eq] at hstep
  exact hstep

-- entry_kind: Builder
-- flag_span_iic_succ: Set.Iic decomposition + span_union + IH advances W(n+1) to W(n+2)
-- Splits Iic ⟨n+1,_⟩ = Iic ⟨n,_⟩ ∪ {⟨n+1,_⟩}, applies span_union, rewrites by IH, closes
-- with the chain hypothesis hchain at index ⟨n+1, hn⟩.
theorem flag_span_iic_succ :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V)
      (v : Fin (Module.finrank K V) → V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ n, n < Module.finrank K V →
        ∃ vnext, vnext ∈ W (n + 1) ∧
          W n ⊔ Submodule.span K {vnext} = W (n + 1)) →
      (∀ j : Fin (Module.finrank K V),
        W j.val ⊔ Submodule.span K {v j} = W (j.val + 1)) →
      ∀ (n : ℕ) (hn : n + 1 < Module.finrank K V),
        Submodule.span K (v '' Set.Iic (⟨n, Nat.lt_of_succ_lt hn⟩ :
            Fin (Module.finrank K V))) = W (n + 1) →
        Submodule.span K (v '' Set.Iic (⟨n + 1, hn⟩ : Fin (Module.finrank K V)))
    = W (n + 2) := by
  intro K _ V _ _ _ W v _ _ _ _ hchain n hn IH
  have hn' := Nat.lt_of_succ_lt hn
  have hIic : Set.Iic (⟨n + 1, hn⟩ : Fin (Module.finrank K V)) =
      Set.Iic (⟨n, hn'⟩ : Fin (Module.finrank K V)) ∪ {⟨n + 1, hn⟩} := by
    ext ⟨k, hk⟩
    simp only [Set.mem_Iic, Set.mem_union, Set.mem_singleton_iff,
               Fin.mk_le_mk, Fin.mk.injEq]
    omega
  rw [hIic, Set.image_union, Set.image_singleton, Submodule.span_union, IH]
  exact hchain ⟨n + 1, hn⟩

-- Induct on j.val to lift the per-index chain equation `W j.val ⊔ span {v j} = W (j.val+1)`
-- into the running span equality.  Two simpler sub-goals:
--   * `flag_span_iic_zero` — base case j.val = 0: with `W 0 = ⊥` and the chain step at index 0,
--     `span (v '' Set.Iic 0) = span {v 0} = W 1`.
--   * `flag_span_iic_succ` — step case: given `span (v '' Set.Iic ⟨n,_⟩) = W (n+1)`, the chain
--     step at index n+1 promotes it to `span (v '' Set.Iic ⟨n+1,_⟩) = W (n+2)`.
-- Combinator: `Nat.rec` on the underlying ℕ of `j.val`, then apply at `j.val, j.isLt`.
theorem flag_seq_span_iic_from_step :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V)
      (v : Fin (Module.finrank K V) → V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ n, n < Module.finrank K V →
        ∃ vnext, vnext ∈ W (n + 1) ∧
          W n ⊔ Submodule.span K {vnext} = W (n + 1)) →
      (∀ j : Fin (Module.finrank K V),
        W j.val ⊔ Submodule.span K {v j} = W (j.val + 1)) →
      ∀ j : Fin (Module.finrank K V),
        Submodule.span K (v '' Set.Iic j) = W (j.val + 1)  := by
  intro K _ V _ _ _ W v hW0 hWmono hWrank hext hstep j
  have h_base := flag_span_iic_zero W v hW0 hWmono hWrank hext hstep
  have h_succ := flag_span_iic_succ W v hW0 hWmono hWrank hext hstep
  have hgen : ∀ (n : ℕ) (hn : n < Module.finrank K V),
      Submodule.span K (v '' Set.Iic (⟨n, hn⟩ : Fin (Module.finrank K V)))
        = W (n + 1) := by
    intro n
    induction n with
    | zero => intro h; exact h_base h
    | succ k ih => intro hkn; exact h_succ k hkn (ih (Nat.lt_of_succ_lt hkn))
  simpa using hgen j.val j.isLt

-- flag_seq_choose_step: packages pointwise Classical.choose of hext into v : Fin d → V
theorem flag_seq_choose_step :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ n, n < Module.finrank K V →
        ∃ vnext, vnext ∈ W (n + 1) ∧
          W n ⊔ Submodule.span K {vnext} = W (n + 1)) →
      ∃ v : Fin (Module.finrank K V) → V,
        ∀ j : Fin (Module.finrank K V),
          W j.val ⊔ Submodule.span K {v j} = W (j.val + 1) := by
  intro K _ V _ _ _ W _h0 _hmono _hrank hext
  exact ⟨fun j => Classical.choose (hext j.val j.isLt),
         fun j => (Classical.choose_spec (hext j.val j.isLt)).2⟩

-- Decompose the iterative-flag construction into two pieces:
-- (1) `flag_seq_choose_step` packages the pointwise `∃ vnext` (from `hext`) into a single
--     function `v : Fin d → V` carrying the chain-step equation per index — a Classical.choice
--     repackaging that strips off the existential layer.
-- (2) `flag_seq_span_iic_from_step` runs the induction on `j.val`: with `W 0 = ⊥` as the base
--     and the per-step chain equation, the span of `v '' Set.Iic j` advances by one along `W`.
-- Combining (1) and (2): pick `v` via (1), conclude the span equality via (2), package the ∃.
theorem flag_seq_build_from_extends :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ n, n < Module.finrank K V →
        ∃ vnext, vnext ∈ W (n + 1) ∧
          W n ⊔ Submodule.span K {vnext} = W (n + 1)) →
      ∃ v : Fin (Module.finrank K V) → V,
        ∀ j : Fin (Module.finrank K V),
          Submodule.span K (v '' Set.Iic j) = W (j.val + 1)  := by
  intro K _ V _ _ _ W hW0 hWmono hWrank hext
  have h_choose := flag_seq_choose_step W hW0 hWmono hWrank hext
  obtain ⟨v, hv⟩ := h_choose
  have h_span := flag_seq_span_iic_from_step W v hW0 hWmono hWrank hext hv
  exact ⟨v, h_span⟩

-- entry_kind: Builder
-- flag_dim_step_existence: finrank inequality forces W(j+1) ⊋ U
theorem flag_dim_step_existence :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      ∀ (j : ℕ), j < Module.finrank K V →
      ∀ (U : Submodule K V), U ≤ W (j + 1) → Module.finrank K U = j →
      ∃ v, v ∈ W (j + 1) ∧ v ∉ U := by
  intro K _instK V _instAG _instMod _instFD W _hW0 _hMono hrank j hj U hU hUrank
  -- finrank K (W (j+1)) = j+1 since j < finrank K V
  have hrankWj1 : Module.finrank K (W (j + 1)) = j + 1 := by
    rw [hrank (j + 1)]
    simp [Nat.min_eq_left (Nat.succ_le_of_lt hj)]
  -- U ≠ W(j+1) because their ranks differ
  have hne : U ≠ W (j + 1) := by
    intro heq
    rw [heq] at hUrank
    omega
  -- U ⊊ W(j+1)
  have hslt : U < W (j + 1) := lt_of_le_of_ne hU hne
  exact (SetLike.exists_of_lt hslt)

-- flag_step_extends_span: for each step n < finrank K V, W(n+1) = W(n) ⊔ span K {vnext}
-- for some vnext ∈ W(n+1); apply the step-existence hypothesis with U := W n, then close
-- W(n+1) ≤ W(n) ⊔ span K {vnext} via equal finrank + containment.
theorem flag_step_extends_span :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ (j : ℕ), j < Module.finrank K V →
        ∀ (U : Submodule K V), U ≤ W (j + 1) → Module.finrank K U = j →
        ∃ v, v ∈ W (j + 1) ∧ v ∉ U) →
      ∀ n, n < Module.finrank K V →
        ∃ vnext, vnext ∈ W (n + 1) ∧
          W n ⊔ Submodule.span K {vnext} = W (n + 1) := by
  intro K _ V _ _ _ W _hW0 hWmono hWrank hstep n hn
  have hrank_n : Module.finrank K (W n) = n := by
    have := hWrank n
    simp [Nat.min_eq_left (Nat.le_of_lt hn)] at this
    exact this
  have hn_step : W n ≤ W (n + 1) := hWmono n
  obtain ⟨vnext, hvnext_mem, hvnext_notin⟩ := hstep n hn (W n) hn_step hrank_n
  refine ⟨vnext, hvnext_mem, ?_⟩
  apply le_antisymm
  · apply sup_le hn_step
    exact Submodule.span_le.mpr (Set.singleton_subset_iff.mpr hvnext_mem)
  · have hrank_sup : Module.finrank K ((W n ⊔ Submodule.span K {vnext} : Submodule K V)) =
        n + 1 := by
      rw [Submodule.finrank_sup_span_singleton hvnext_notin, hrank_n]
    have hrank_next : Module.finrank K (W (n + 1)) = n + 1 := by
      have := hWrank (n + 1)
      simp [Nat.min_eq_left hn] at this
      exact this
    have hle : W n ⊔ Submodule.span K {vnext} ≤ W (n + 1) := by
      apply sup_le hn_step
      exact Submodule.span_le.mpr (Set.singleton_subset_iff.mpr hvnext_mem)
    exact (Submodule.eq_of_le_of_finrank_eq hle (hrank_sup.trans hrank_next.symm)).symm.le

-- Decompose into (1) a packaged step lemma — under the parent's step-existence and
-- finrank hypotheses, for each n < finrank K V there is `vnext ∈ W (n+1)` with
-- `W n ⊔ span K {vnext} = W (n+1)` (folds the dimension argument into the step) —
-- and (2) a pure iterative construction — given that packaged step, build the
-- `Fin (finrank K V) → V` sequence and prove the span equality by induction on j.
-- (1) is a one-shot rank/sup argument; (2) carries the dependent recursion.
theorem flag_seq_build_from_step :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ (j : ℕ), j < Module.finrank K V →
        ∀ (U : Submodule K V), U ≤ W (j + 1) → Module.finrank K U = j →
        ∃ v, v ∈ W (j + 1) ∧ v ∉ U) →
      ∃ v : Fin (Module.finrank K V) → V,
        ∀ j : Fin (Module.finrank K V),
          Submodule.span K (v '' Set.Iic j) = W (j.val + 1)  := by
  intro K _instK V _instAG _instMod _instFD W hW0 hmono hrank hstep
  have h_extends := flag_step_extends_span W hW0 hmono hrank hstep
  exact flag_seq_build_from_extends W hW0 hmono hrank h_extends

-- Decompose into (1) the dimensional step-existence lemma — given any submodule U ≤ W(j+1)
-- of dimension j, there is a vector in W(j+1) outside U — and (2) a recursive construction
-- that consumes that step-existence to build the full Fin n → V sequence and proves the
-- initial-span equality by induction on j. (1) is purely a finrank inequality; (2) carries
-- the dependent recursion + induction-on-j proof obligation.
theorem flag_vector_seq_exists :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      ∃ v : Fin (Module.finrank K V) → V,
        ∀ j : Fin (Module.finrank K V),
          Submodule.span K (v '' Set.Iic j) = W (j.val + 1)  := by
  intro K _ V _ _ _ W hW0 hWmono hWdim
  have h_step := flag_dim_step_existence W hW0 hWmono hWdim
  exact flag_seq_build_from_step W hW0 hWmono hWdim h_step

-- basis_from_flag_spans: v with initial spans matching the flag is itself a basis
-- v spans V (last span = W n = ⊤) and is LI (Fintype.card ≤ finrank span = n);
-- Basis.mk packages it, and mk_apply shows b = v pointwise so span conditions transfer.
theorem basis_from_flag_spans :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      ∀ v : Fin (Module.finrank K V) → V,
        (∀ j : Fin (Module.finrank K V),
            Submodule.span K (v '' Set.Iic j) = W (j.val + 1)) →
        ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
          ∀ j : Fin (Module.finrank K V),
            Submodule.span K (b '' Set.Iic j) = W (j.val + 1) := by
  intro K _ V _ _ _ W _hW0 _hWmono hWrank v hv
  -- Step 1: W (finrank K V) = ⊤
  have hWn_top : W (Module.finrank K V) = ⊤ := by
    apply Submodule.eq_top_of_finrank_eq
    have h := hWrank (Module.finrank K V)
    simp only [min_self] at h; exact h
  -- Step 2: span K (Set.range v) = ⊤
  have hrange_top : Submodule.span K (Set.range v) = ⊤ := by
    rcases Nat.eq_zero_or_pos (Module.finrank K V) with hn | hn
    · -- finrank = 0: V is trivial, so span ∅ = ⊥ = ⊤
      have hIsEmpty : IsEmpty (Fin (Module.finrank K V)) := by rw [hn]; exact Fin.isEmpty
      rw [Set.range_eq_empty_iff.mpr hIsEmpty, Submodule.span_empty]
      apply Submodule.eq_top_of_finrank_eq
      simp [finrank_bot K V, hn]
    · -- finrank > 0: use the last index j = ⟨n-1, ...⟩
      let j : Fin (Module.finrank K V) := ⟨Module.finrank K V - 1,
        Nat.sub_lt hn Nat.one_pos⟩
      have hjval : j.val + 1 = Module.finrank K V := Nat.succ_pred_eq_of_pos hn
      have hIic_univ : Set.Iic j = Set.univ := by
        ext i
        simp only [Set.mem_Iic, Set.mem_univ, iff_true]
        exact Nat.le_sub_one_of_lt i.isLt
      rw [show Set.range v = v '' Set.Iic j from by rw [hIic_univ, Set.image_univ],
          hv j, hjval]
      exact hWn_top
  -- Step 3: LinearIndependent K v via linearIndependent_iff_card_le_finrank_span
  have hLI : LinearIndependent K v := by
    rw [linearIndependent_iff_card_le_finrank_span]
    simp only [Set.finrank, Fintype.card_fin]
    rw [hrange_top, finrank_top]
  -- Step 4: Package v as a basis; b i = v i by mk_apply, so span conditions transfer
  exact ⟨Module.Basis.mk hLI hrange_top.symm.le, fun j => by
    have hbv : ⇑(Module.Basis.mk hLI hrange_top.symm.le) = v :=
      funext (Module.Basis.mk_apply hLI hrange_top.symm.le)
    rw [hbv]; exact hv j⟩

-- Decompose into (1) constructing a function v : Fin n → V whose initial spans match the
-- flag, and (2) packaging such a v as a Module.Basis carrying the same property.
-- (1) carries the inductive / dimension-step content (pick v_j ∈ W(j+1) extending v_{<j});
-- (2) is a basis-vs-function bookkeeping bridge: range v spans W n = ⊤ + |Fin n| = finrank,
-- so v is a basis.
theorem flag_adapted_basis_exists :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
        ∀ j : Fin (Module.finrank K V),
          Submodule.span K (b '' Set.Iic j) = W (j.val + 1)  := by
  intro K _ V _ _ _ W hW0 hWmono hWdim
  have h_flag_vector_seq_exists := flag_vector_seq_exists W hW0 hWmono hWdim
  have h_basis_from_flag_spans := basis_from_flag_spans W hW0 hWmono hWdim
  obtain ⟨v, hv⟩ := h_flag_vector_seq_exists
  exact h_basis_from_flag_spans v hv

-- Reduce to building a flag-adapted basis (pure linear algebra, no T): a basis b
-- with span(b '' Set.Iic j) = W (j.val + 1). T-invariance of W (j.val + 1) then
-- transports T (b j) into that span, since b j ∈ W (j.val + 1).
theorem adapted_basis_of_flag :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V)
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ i, ∀ v ∈ W i, T v ∈ W i) →
      ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
        ∀ j : Fin (Module.finrank K V),
          T (b j) ∈ Submodule.span K (b '' Set.Iic j)  := by
  intro K _ V _ _ _ T W hW0 hWmono hWdim hWinv
  have h_flag_adapted_basis_exists := flag_adapted_basis_exists W hW0 hWmono hWdim
  obtain ⟨b, hspan⟩ := h_flag_adapted_basis_exists
  refine ⟨b, fun j => ?_⟩
  have hbj_in_W : b j ∈ W (j.val + 1) := by
    rw [← hspan j]
    exact Submodule.subset_span ⟨j, Set.mem_Iic.mpr le_rfl, rfl⟩
  have hTbj_in_W : T (b j) ∈ W (j.val + 1) := hWinv _ _ hbj_in_W
  rw [← hspan j] at hTbj_in_W
  exact hTbj_in_W

end Library.LinearAlgebra.SchurTriangularization.FlagBasis
