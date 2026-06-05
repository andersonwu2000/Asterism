import Mathlib

namespace Library.LinearAlgebra.CourantFischer.EigenbasisExpansion

-- inner_tx_eigenvector: ⟪T x, eᵢ⟫ = λᵢ · (repr x i) via symmetry +
-- apply_eigenvectorBasis + inner_smul_right + repr_apply_apply + real_inner_comm
theorem inner_tx_eigenvector
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n)
    (x : E) (i : Fin n) :
    inner ℝ (T x) ((hT.eigenvectorBasis hn) i)
      = hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i := by
  rw [hT x, hT.apply_eigenvectorBasis hn i, inner_smul_right,
      OrthonormalBasis.repr_apply_apply, real_inner_comm]
  simp

-- Rayleigh numerator in the eigenbasis: expand ⟪Tx,x⟫ over the orthonormal
-- eigenbasis via `sum_inner_mul_inner`; each cross term ⟪Tx,bᵢ⟫·⟪bᵢ,x⟫ reduces
-- (sub-goal `inner_Tx_eigenvector`) to λᵢ·(repr x i), giving λᵢ·(repr x i)².
theorem rayleigh_numerator_eigenbasis
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (x : E) :
    inner ℝ (T x) x =
      ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2  := by
  have hA := fun i => inner_tx_eigenvector hT hn x i
  rw [← OrthonormalBasis.sum_inner_mul_inner (hT.eigenvectorBasis hn) (T x) x]
  apply Finset.sum_congr rfl
  intro i _
  rw [hA i, OrthonormalBasis.repr_apply_apply]
  ring

-- norm_sq_eq_sum_repr_sq: Parseval identity — ‖x‖² equals sum of squared eigenbasis
-- repr coefficients, via the isometry OrthonormalBasis.repr and PiLp.norm_sq_eq_of_L2.
theorem norm_sq_eq_sum_repr_sq
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (x : E) :
    ‖x‖ ^ 2 = ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 := by
  have hnorm : ‖(hT.eigenvectorBasis hn).repr x‖ = ‖x‖ :=
    LinearIsometryEquiv.norm_map _ x
  rw [← hnorm]
  rw [PiLp.norm_sq_eq_of_L2]
  congr 1; ext i
  exact Real.norm_eq_abs _ ▸ sq_abs _

-- norm_sq_eq_sum_repr_sq_2: Parseval identity — ‖x‖² equals sum of squared
-- orthonormal-basis representation coefficients, via repr_apply_apply + sum_sq_inner_right.
theorem norm_sq_eq_sum_repr_sq_2
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (x : E) :
    ‖x‖ ^ 2 = ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 := by
  simp only [OrthonormalBasis.repr_apply_apply]
  exact ((hT.eigenvectorBasis hn).sum_sq_inner_right x).symm

theorem rayleigh_numerator_in_eigenbasis
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (x : E) :
    @inner ℝ E _ (T x) x =
      ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 := by apply rayleigh_numerator_eigenbasis <;> assumption

theorem numerator_eigenbasis_expand
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (x : E) :
    (inner ℝ (T x) x : ℝ) =
      ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 := by apply rayleigh_numerator_eigenbasis <;> assumption

-- Orthonormality: x in span of bottom modes {b_j : m ≤ j} is ⟂ to b_i for i < m.
-- span_induction on the membership; the linear functional ⟪b i, ·⟫ vanishes on each
-- generator b_j (i ≠ j since i < m ≤ j by orthonormality) and is closed under +/•.
-- Direct leaf — no sub-goals.
theorem inner_eq_zero_of_mem_span_high
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    {n : ℕ} (b : OrthonormalBasis (Fin n) ℝ E) (m : ℕ) :
    ∀ x : E, x ∈ Submodule.span ℝ (b '' {i : Fin n | m ≤ (i : ℕ)}) →
      ∀ i : Fin n, (i : ℕ) < m → @inner ℝ E _ (b i) x = 0  := by
  intro x hx i hi
  induction hx using Submodule.span_induction with
  | mem y hy =>
      obtain ⟨j, hj, rfl⟩ := hy
      have hij : i ≠ j := by
        intro h
        rw [h] at hi
        exact absurd hi (not_lt.mpr hj)
      exact b.orthonormal.2 hij
  | zero => simp
  | add y z _ _ ihy ihz =>
      rw [inner_add_right, ihy, ihz, add_zero]
  | smul a y _ ih =>
      rw [inner_smul_right, ih, mul_zero]

-- orthobasis_repr_vanish_outside_span: repr coefficient vanishes at index i
-- when x lies in the span of the sub-family indexed by P and ¬P i holds,
-- because b i is orthogonal to every generator and hence to the whole span.
theorem orthobasis_repr_vanish_outside_span
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    {n : ℕ} (b : OrthonormalBasis (Fin n) ℝ E)
    (P : Fin n → Prop)
    (x : E) (hx : x ∈ Submodule.span ℝ (b '' {j : Fin n | P j}))
    (i : Fin n) (hi : ¬ P i) :
    b.repr x i = 0 := by
  simp only [OrthonormalBasis.repr_apply_apply]
  apply Submodule.inner_left_of_mem_orthogonal hx
  rw [Submodule.mem_orthogonal']
  intro u hu
  refine Submodule.span_induction (p := fun u _ => inner ℝ (b i) u = (0 : ℝ)) ?_ ?_ ?_ ?_ hu
  · rintro s ⟨j, hPj, rfl⟩
    exact b.orthonormal.inner_eq_zero (fun h => hi (h ▸ hPj))
  · simp
  · intro v w _ _ hv hw
    rw [inner_add_right, hv, hw, add_zero]
  · intro r v _ hv
    rw [inner_smul_right, hv, mul_zero]

-- Term-wise bound: ∑ λᵢ·(repr x i)² ≤ λ_k·∑ (repr x i)², via `Finset.sum_le_sum`.
-- For i < k the coefficient `repr x i = ⟪eᵢ, x⟫ = 0` (hzero) kills both sides;
-- for k ≤ i, `eigenvalues_antitone` gives λᵢ ≤ λ_k and `(repr x i)² ≥ 0` lifts it.
-- Direct leaf — no sub-goals.
theorem weighted_eigenvalue_sum_le
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) (x : E)
    (hzero : ∀ i : Fin n, (i : ℕ) < (k : ℕ) →
      @inner ℝ E _ ((hT.eigenvectorBasis hn) i) x = 0) :
    ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2
      ≤ hT.eigenvalues hn k * ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2  := by
  rw [Finset.mul_sum]
  apply Finset.sum_le_sum
  intro i _
  rcases lt_or_ge (i : ℕ) (k : ℕ) with hik | hik
  · have hz : (hT.eigenvectorBasis hn).repr x i = 0 := by
      rw [OrthonormalBasis.repr_apply_apply]
      exact hzero i hik
    rw [hz]; simp
  · have hle : hT.eigenvalues hn i ≤ hT.eigenvalues hn k :=
      hT.eigenvalues_antitone hn hik
    exact mul_le_mul_of_nonneg_right hle (sq_nonneg _)

-- Termwise weighted-sum bound: distribute λ_k over the sum, then compare term by term.
-- Each term λ_k·rᵢ² ≤ λᵢ·rᵢ²: for i ≤ k the antitone (decreasing) spectrum gives λ_k ≤ λᵢ
-- and rᵢ² ≥ 0; for k < i the high mode vanishes (hv), making both sides 0.
-- Direct (sorry-free) leaf proof: Finset.mul_sum + Finset.sum_le_sum, no sub-goals.
theorem weighted_eigenvalue_sum_ge
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) (x : E)
    (hv : ∀ i : Fin n, (k : ℕ) < (i : ℕ) →
      (hT.eigenvectorBasis hn).repr x i = 0) :
    hT.eigenvalues hn k * (∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2)
      ≤ ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2  := by
  rw [Finset.mul_sum]
  apply Finset.sum_le_sum
  intro i _
  by_cases h : (i : ℕ) ≤ (k : ℕ)
  · apply mul_le_mul_of_nonneg_right
    · exact hT.eigenvalues_antitone hn (Fin.le_def.mpr h)
    · positivity
  · rw [hv i (not_le.mp h)]
    simp

end Library.LinearAlgebra.CourantFischer.EigenbasisExpansion
