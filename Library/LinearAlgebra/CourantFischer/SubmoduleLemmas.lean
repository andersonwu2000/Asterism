import Mathlib

namespace Library.LinearAlgebra.CourantFischer.SubmoduleLemmas

-- Dimension count: dim(U⊓W)+dim(U⊔W)=dim U+dim W and dim(U⊔W)≤n force dim(U⊓W)>0.
-- Hence U⊓W≠⊥ yields a nonzero vector lying in both U and W. Direct leaf proof.
theorem subspace_inter_nonzero_of_finrank
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    (U W : Submodule ℝ E) {n : ℕ} (hn : Module.finrank ℝ E = n)
    (h : n < Module.finrank ℝ U + Module.finrank ℝ W) :
    ∃ x : E, x ∈ U ∧ x ∈ W ∧ x ≠ 0  := by
  have hcard : Module.finrank ℝ (U ⊔ W : Submodule ℝ E) + Module.finrank ℝ (U ⊓ W : Submodule ℝ E)
      = Module.finrank ℝ U + Module.finrank ℝ W := Submodule.finrank_sup_add_finrank_inf_eq U W
  have hle : Module.finrank ℝ (U ⊔ W : Submodule ℝ E) ≤ n := hn ▸ Submodule.finrank_le _
  have hpos : 0 < Module.finrank ℝ (U ⊓ W : Submodule ℝ E) := by omega
  have hne : (U ⊓ W : Submodule ℝ E) ≠ ⊥ := by
    intro hbot
    rw [hbot] at hpos
    simp at hpos
  obtain ⟨x, hx, hx0⟩ := Submodule.exists_mem_ne_zero_of_ne_bot hne
  exact ⟨x, (Submodule.mem_inf.mp hx).1, (Submodule.mem_inf.mp hx).2, hx0⟩

theorem subspace_inter_nonzero
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] (U W : Submodule ℝ E) {n : ℕ}
    (hn : Module.finrank ℝ E = n)
    (h : n < Module.finrank ℝ U + Module.finrank ℝ W) :
    ∃ x : E, x ∈ U ∧ x ∈ W ∧ x ≠ 0 := by apply subspace_inter_nonzero_of_finrank <;> assumption

-- exists_subspace_finrank: span of first k+1 basis vectors has finrank k+1,
-- using Module.finBasis + LinearIndependent.comp + finrank_span_eq_card
theorem exists_subspace_finrank
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E]
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    ∃ S : Submodule ℝ E, Module.finrank ℝ S = (k : ℕ) + 1 := by
  have hkn : (k : ℕ) + 1 ≤ Module.finrank ℝ E := by rw [hn]; exact k.isLt
  let b := Module.finBasis ℝ E
  let f : Fin ((k : ℕ) + 1) → E := fun i => b ⟨i, Nat.lt_of_lt_of_le i.isLt hkn⟩
  have hinj : Function.Injective (fun i : Fin ((k : ℕ) + 1) =>
      (⟨i.val, Nat.lt_of_lt_of_le i.isLt hkn⟩ : Fin (Module.finrank ℝ E))) := by
    intro a c h
    simp only at h
    have hval : a.val = c.val := by
      have := congrArg (Fin.val (n := Module.finrank ℝ E)) h
      simpa using this
    exact Fin.ext hval
  have hli : LinearIndependent ℝ f := b.linearIndependent.comp _ hinj
  exact ⟨Submodule.span ℝ (Set.range f),
    by rw [finrank_span_eq_card hli, Fintype.card_fin]⟩

-- exists_nonzero_mem_of_finrank_pos: a submodule of positive finrank contains a nonzero element
-- Uses S ≠ ⊥ (from finrank > 0) and Submodule.exists_mem_ne_zero_of_ne_bot.
theorem exists_nonzero_mem_of_finrank_pos
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E]
    (S : Submodule ℝ E) (m : ℕ) (h : Module.finrank ℝ S = m + 1) :
    ∃ x ∈ S, x ≠ 0 := by
  have hne : S ≠ ⊥ := by
    intro heq
    have : Module.finrank ℝ S = 0 := heq ▸ finrank_bot ℝ E
    omega
  exact Submodule.exists_mem_ne_zero_of_ne_bot hne

-- card_fin_subtype_ge: Fintype.card of {i : Fin n // m ≤ i} equals n - m,
-- proved via explicit bijection with Fin (n - m) sending i ↦ i - m.
theorem card_fin_subtype_ge (n m : ℕ) :
    Fintype.card {i : Fin n // m ≤ (i : ℕ)} = n - m := by
  rw [← Fintype.card_fin (n - m)]
  apply Fintype.card_congr
  refine {
    toFun := fun ⟨⟨i, hi⟩, hm⟩ => ⟨i - m, by omega⟩
    invFun := fun ⟨j, hj⟩ => ⟨⟨m + j, by omega⟩, Nat.le_add_right m j⟩
    left_inv := ?_
    right_inv := ?_
  }
  · intro ⟨⟨i, hi⟩, hm⟩
    simp only [] at hm ⊢
    ext
    simp
    omega
  · intro ⟨j, hj⟩
    ext
    simp

-- linear_independent_basis_subset: orthonormal basis restriction to {i : Fin n // m ≤ i} is
-- linearly independent — orthonormality of the subfamily (injective reindex) gives linear indep.
theorem linear_independent_basis_subset
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {n : ℕ} (b : OrthonormalBasis (Fin n) ℝ E) (m : ℕ) :
    LinearIndependent ℝ (fun i : {i : Fin n // m ≤ (i : ℕ)} => b (i : Fin n)) := by
  apply Orthonormal.linearIndependent
  exact b.orthonormal.comp _ Subtype.val_injective

-- Span of an orthonormal-basis subset has finrank = cardinality of the index set.
-- hLI: the restricted family {b i : m ≤ i} is linearly independent (orthonormal ⇒ indep).
-- hcard: there are n − m indices i : Fin n with m ≤ i.
-- Rewrite the image as a range, then `finrank_span_eq_card` turns the goal into the count.
theorem finrank_span_image_high
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {n : ℕ} (b : OrthonormalBasis (Fin n) ℝ E) (m : ℕ) :
    Module.finrank ℝ (Submodule.span ℝ (b '' {i : Fin n | m ≤ (i : ℕ)})) = n - m  := by
  have hLI : LinearIndependent ℝ (fun i : {i : Fin n // m ≤ (i : ℕ)} => b (i : Fin n)) :=
    linear_independent_basis_subset b m
  have hcard : Fintype.card {i : Fin n // m ≤ (i : ℕ)} = n - m :=
    card_fin_subtype_ge n m
  have himg : b '' {i : Fin n | m ≤ (i : ℕ)}
      = Set.range (fun i : {i : Fin n // m ≤ (i : ℕ)} => b (i : Fin n)) :=
    Set.image_eq_range _ _
  rw [himg, finrank_span_eq_card hLI, hcard]

-- topeig_eigenbasis_linindep_on_set: linear independence of eigenvectorBasis restricted to {i ≤ k}
-- via orthonormality: eigenvectorBasis is orthonormal, any subfamily (injective reindex) is too

theorem topeig_eigenbasis_linindep_on_set
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    LinearIndependent ℝ
      (fun i : ↥{i : Fin n | (i : ℕ) ≤ (k : ℕ)} => (hT.eigenvectorBasis hn) (i : Fin n)) := by
  apply Orthonormal.linearIndependent
  exact (hT.eigenvectorBasis hn).orthonormal.comp _ Subtype.val_injective

-- topeig_le_subtype_card: the initial segment {i : Fin n | i ≤ k} has cardinality k+1,
-- via Fin.card_Iic after identifying the filter with Finset.Iic k.
theorem topeig_le_subtype_card {n : ℕ} (k : Fin n) :
    Fintype.card {i : Fin n // (i : ℕ) ≤ (k : ℕ)} = (k : ℕ) + 1 := by
  rw [Fintype.card_subtype]
  have h : Finset.univ.filter (fun x : Fin n => (x : ℕ) ≤ (k : ℕ)) = Finset.Iic k := by
    ext x; simp [Finset.mem_Iic]
  rw [h]
  exact Fin.card_Iic k

end Library.LinearAlgebra.CourantFischer.SubmoduleLemmas
