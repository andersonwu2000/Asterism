import Mathlib

/-!
# Submodule lemmas for the Courant–Fischer theorem

This file collects auxiliary results about submodule dimensions, spanning sets, and linear
independence of orthonormal-basis subfamilies used in the proof of the Courant–Fischer min-max
theorem.  The key facts are: two subspaces of complementary large dimension must intersect
non-trivially; a submodule of positive rank contains a nonzero vector; and a restriction of an
orthonormal basis to an index subset is linearly independent with computable span rank.
-/

namespace Library.LinearAlgebra.CourantFischer.SubmoduleLemmas

/-- If the sum of the finranks of two subspaces `U` and `W` of an `n`-dimensional inner product
space exceeds `n`, then `U ∩ W` contains a nonzero vector.  The proof uses the
dimension identity `finrank(U ⊔ W) + finrank(U ⊓ W) = finrank U + finrank W` together with
the bound `finrank(U ⊔ W) ≤ n` to deduce that `U ⊓ W ≠ ⊥`. -/
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

/-- In a finite-dimensional inner product space of dimension `n`, for each `k : Fin n` there
exists a submodule of finrank `k + 1`.  The witness is the span of the first `k + 1` vectors of
the canonical `Module.finBasis`. -/
theorem exists_subspace_finrank
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E]
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    ∃ S : Submodule ℝ E, Module.finrank ℝ S = (k : ℕ) + 1 := by
  have hkn : (k : ℕ) + 1 ≤ Module.finrank ℝ E := by rw [hn]; exact k.isLt
  have hli : LinearIndependent ℝ (fun i : Fin ((k : ℕ) + 1) =>
      (Module.finBasis ℝ E) (Fin.castLE hkn i)) :=
    (Module.finBasis ℝ E).linearIndependent.comp _ (Fin.castLE_injective hkn)
  exact ⟨Submodule.span ℝ (Set.range _),
    by rw [finrank_span_eq_card hli, Fintype.card_fin]⟩

/-- A submodule `S` with `Module.finrank ℝ S = m + 1` contains a nonzero element.  The rank
hypothesis rules out `S = ⊥`, and then `Submodule.exists_mem_ne_zero_of_ne_bot` supplies the
witness. -/
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

/-- The number of indices `i : Fin n` satisfying `m ≤ i` equals `n - m`.  The proof constructs
an explicit `Equiv` between `{i : Fin n // m ≤ i}` and `Fin (n - m)` via the shift `i ↦ i - m`. -/
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

/-- The restriction of an orthonormal basis `b` of `E` to the index subfamily
`{i : Fin n // m ≤ i}` is linearly independent.  This follows because orthonormality is
preserved under injective reindexing. -/
theorem linear_independent_basis_subset
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {n : ℕ} (b : OrthonormalBasis (Fin n) ℝ E) (m : ℕ) :
    LinearIndependent ℝ (fun i : {i : Fin n // m ≤ (i : ℕ)} => b (i : Fin n)) := by
  apply Orthonormal.linearIndependent
  exact b.orthonormal.comp _ Subtype.val_injective

/-- The span of the orthonormal-basis vectors indexed by `{i : Fin n | m ≤ i}` has finrank
`n - m`.  The proof rewrites the image as a range, applies `finrank_span_eq_card` using the linear
independence from `linear_independent_basis_subset`, and counts the index set via
`card_fin_subtype_ge`. -/
theorem finrank_span_image_high
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {n : ℕ} (b : OrthonormalBasis (Fin n) ℝ E) (m : ℕ) :
    Module.finrank ℝ (Submodule.span ℝ (b '' {i : Fin n | m ≤ (i : ℕ)})) = n - m  := by
  have hLI := linear_independent_basis_subset b m
  have himg : b '' {i : Fin n | m ≤ (i : ℕ)} =
      Set.range (fun i : {i : Fin n // m ≤ (i : ℕ)} => b (i : Fin n)) :=
    Set.image_eq_range _ _
  rw [himg, finrank_span_eq_card hLI, card_fin_subtype_ge]

/-- The eigenvector-basis vectors of a symmetric operator `T`, restricted to the initial segment
`{i : Fin n | i ≤ k}`, are linearly independent.  Orthonormality of the eigenvector basis under
injective reindexing yields the result. -/
theorem topeig_eigenbasis_linindep_on_set
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    LinearIndependent ℝ
      (fun i : ↥{i : Fin n | (i : ℕ) ≤ (k : ℕ)} => (hT.eigenvectorBasis hn) (i : Fin n)) := by
  apply Orthonormal.linearIndependent
  exact (hT.eigenvectorBasis hn).orthonormal.comp _ Subtype.val_injective

/-- The initial segment `{i : Fin n | i ≤ k}` has cardinality `k + 1`.  The count follows from
`Fin.card_Iic` after identifying the subtype filter with `Finset.Iic k`. -/
theorem topeig_le_subtype_card {n : ℕ} (k : Fin n) :
    Fintype.card {i : Fin n // (i : ℕ) ≤ (k : ℕ)} = (k : ℕ) + 1 := by rw [Fintype.card_subtype, show Finset.univ.filter (fun x : Fin n => (x : ℕ) ≤ (k : ℕ)) = Finset.Iic k from by ext x; simp [Finset.mem_Iic]]; exact Fin.card_Iic k

end Library.LinearAlgebra.CourantFischer.SubmoduleLemmas
