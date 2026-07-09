import Library.LinearAlgebra.CourantFischer.RayleighBounds
import Library.LinearAlgebra.CourantFischer.SubmoduleLemmas
import Library.LinearAlgebra.CourantFischer.TestSubspaces
import Mathlib

open Library.LinearAlgebra.CourantFischer.RayleighBounds
open Library.LinearAlgebra.CourantFischer.SubmoduleLemmas
open Library.LinearAlgebra.CourantFischer.TestSubspaces

/-!
# Courant–Fischer min-max theorem

This file establishes the Courant–Fischer min-max characterisation of eigenvalues of a
symmetric linear operator on a finite-dimensional real inner product space: the `k`-th
eigenvalue equals the supremum over all `(k+1)`-dimensional subspaces `S` of the
infimum of the Rayleigh quotient `⟨Tx, x⟩ / ‖x‖²` over nonzero `x ∈ S`.

The proof splits into two inequalities assembled by `le_antisymm`:
- **Upper bound** (`sup_inf_rayleigh_le_eigenvalue`): for every `(k+1)`-dim `S`, a
  dimension count forces a nonzero intersection with the bottom `(n−k)`-eigenvector
  subspace, whose Rayleigh quotient is bounded above by `λ_k`.
- **Lower bound** (`eigenvalue_le_sup_inf_rayleigh`): the top `(k+1)`-eigenvector span
  is a witness subspace achieving Rayleigh infimum ≥ `λ_k`.
-/

namespace Library.LinearAlgebra.CourantFischer.CourantFischer

/-- For any `(k+1)`-dimensional subspace `S` there exists a nonzero vector `x ∈ S`
whose Rayleigh quotient `⟨Tx, x⟩ / ‖x‖²` is at most the `k`-th eigenvalue of `T`.
The proof intersects `S` with the bottom `(n−k)`-eigenvector subspace `W`; the rank
inequality `(k+1) + (n−k) = n+1 > n` forces `S ⊓ W ≠ ⊥`, and every nonzero element
of `W` has Rayleigh quotient bounded by `λ_k`. -/
theorem exists_vector_rayleigh_le_eigenvalue
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) (S : Submodule ℝ E)
    (hScard : Module.finrank ℝ S = (k : ℕ) + 1) :
    ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
      @inner ℝ E _ (T x) x / ‖x‖ ^ 2 ≤ hT.eigenvalues hn k  := by
  have hk := k.isLt
  obtain ⟨W, hWdim, hWbound⟩ := bottom_eigenspace_exists hT hn k
  obtain ⟨x, hxS, hxW, hx0⟩ :=
    Library.LinearAlgebra.CourantFischer.SubmoduleLemmas.subspace_inter_nonzero_of_finrank S W hn (by omega)
  exact ⟨x, hxS, hx0, hWbound x hxW hx0⟩

/-- For any `(k+1)`-dimensional subspace `S`, the infimum of the Rayleigh quotient
`⟨Tx, x⟩ / ‖x‖²` over nonzero vectors in `S` is at most the `k`-th eigenvalue of `T`.
This follows from `exists_vector_rayleigh_le_eigenvalue` together with `csInf_le` applied
to the boundedness of the Rayleigh set. -/
theorem inf_rayleigh_le_eigenvalue
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) (S : Submodule ℝ E)
    (hScard : Module.finrank ℝ S = (k : ℕ) + 1) :
    sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
      q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2) ≤ hT.eigenvalues hn k  := by
  have h_exists := exists_vector_rayleigh_le_eigenvalue hT hn k S hScard
  have h_bdd := rayleigh_set_bddbelow hT S
  obtain ⟨x, hxS, hx0, hxle⟩ := h_exists
  exact le_trans (csInf_le h_bdd ⟨x, hxS, hx0, rfl⟩) hxle

/-- The `k`-th eigenvalue of `T` is a lower bound for the supremum over all
`(k+1)`-dimensional subspaces of the infimum of the Rayleigh quotient.
The top `(k+1)`-eigenvector span serves as a witness subspace whose Rayleigh infimum
is at least `λ_k`; the conclusion then follows from `le_csSup` using the bounded-above
Rayleigh sup-set. -/
theorem eigenvalue_le_sup_inf_rayleigh
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    hT.eigenvalues hn k ≤
      sSup (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
        Module.finrank ℝ S = (k : ℕ) + 1 ∧
        r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
          q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2))  := by
  have h_bdd := rayleigh_sup_set_bdd_above hT hn k
  have h_exists := exists_test_subspace_inf_ge_eigenvalue hT hn k
  obtain ⟨S, hS, hge⟩ := h_exists
  exact le_trans hge (le_csSup h_bdd ⟨S, hS, rfl⟩)

/-- The supremum over all `(k+1)`-dimensional subspaces of the infimum of the Rayleigh
quotient is at most the `k`-th eigenvalue of `T`.
Applied via `csSup_le`: the index set is nonempty by `exists_subspace_finrank`, and
`inf_rayleigh_le_eigenvalue` provides the pointwise bound for every member. -/
theorem sup_inf_rayleigh_le_eigenvalue
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    sSup (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
        Module.finrank ℝ S = (k : ℕ) + 1 ∧
        r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
          q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)) ≤ hT.eigenvalues hn k  := by
  have h_exists := exists_subspace_finrank hn k
  have h_inf := fun (S : Submodule ℝ E) (hS : Module.finrank ℝ S = (k : ℕ) + 1) =>
    inf_rayleigh_le_eigenvalue hT hn k S hS
  apply csSup_le
  · obtain ⟨S, hS⟩ := h_exists
    exact ⟨_, S, hS, rfl⟩
  · rintro r ⟨S, hScard, rfl⟩
    exact h_inf S hScard

/-- The Courant–Fischer min-max theorem: the `k`-th eigenvalue of a symmetric operator `T`
on an `n`-dimensional real inner product space equals the supremum over all
`(k+1)`-dimensional subspaces `S` of the infimum of the Rayleigh quotient
`⟨Tx, x⟩ / ‖x‖²` over nonzero `x ∈ S`. -/
theorem main {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    hT.eigenvalues hn k =
      sSup (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
        Module.finrank ℝ S = (k : ℕ) + 1 ∧
        r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
          q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)) := by
  exact le_antisymm (eigenvalue_le_sup_inf_rayleigh hT hn k) (sup_inf_rayleigh_le_eigenvalue hT hn k)

end Library.LinearAlgebra.CourantFischer.CourantFischer
