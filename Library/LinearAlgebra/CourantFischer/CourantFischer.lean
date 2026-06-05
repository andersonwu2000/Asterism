import Library.LinearAlgebra.CourantFischer.RayleighBounds
import Library.LinearAlgebra.CourantFischer.SubmoduleLemmas
import Library.LinearAlgebra.CourantFischer.TestSubspaces
import Mathlib

open Library.LinearAlgebra.CourantFischer.RayleighBounds
open Library.LinearAlgebra.CourantFischer.SubmoduleLemmas
open Library.LinearAlgebra.CourantFischer.TestSubspaces

namespace Library.LinearAlgebra.CourantFischer.CourantFischer

-- Courant–Fischer upper bound: a nonzero x ∈ S with Rayleigh ≤ λ_k exists.
-- h_bottom (sub-goal): the bottom (n−k)-eigenvector subspace W has finrank n−k and
--   every nonzero vector in it has Rayleigh ≤ λ_k (the spectral content; drops S).
-- subspace_inter_nonzero (sub-goal, dedupes to the proved dimension-count brick):
--   finrank S + finrank W = (k+1)+(n−k) = n+1 > n forces a nonzero x ∈ S ⊓ W.
-- Combining, that x lies in W so hWbound bounds its Rayleigh by λ_k.
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
    subspace_inter_nonzero S W hn (by omega)
  exact ⟨x, hxS, hx0, hWbound x hxW hx0⟩

-- Courant–Fischer upper bound (per fixed (k+1)-dim S): the inner Rayleigh sInf ≤ λ_k.
-- A dimension count yields a nonzero x ∈ S landing in the bottom eigenspace with
-- Rayleigh ≤ λ_k (h_exists); since that Rayleigh value lies in the bounded-below set
-- (h_bdd), csInf_le + transitivity closes the goal. Both sub-goals drop the sInf layer.
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

-- Lower bound λ_k ≤ sSup via `le_csSup` with the top-(k+1)-eigenvector test subspace.
-- h_bdd (rayleigh_sup_set_bdd_above): the sSup set is bounded above (each member sInf
--   ≤ ‖T‖ by Cauchy–Schwarz), giving the `BddAbove` premise of `le_csSup`.
-- h_exists (exists_test_subspace_inf_ge_eigenvalue): a witness subspace S of finrank k+1
--   whose Rayleigh sInf is ≥ λ_k; it is a member of the sSup set, so λ_k ≤ sInf S ≤ sSup.
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

-- Courant–Fischer upper bound: sSup over (k+1)-dim subspaces of the inner sInf
-- Rayleigh quotient is ≤ eigenvalue k. Closed by `csSup_le`:
--   • h_exists (exists_subspace_finrank): the index set is nonempty — some (k+1)-dim
--     subspace exists, so the sSup has a witness `r`.
--   • h_inf (inf_rayleigh_le_eigenvalue): for EVERY (k+1)-dim S, the inner sInf of the
--     Rayleigh set is ≤ eigenvalue k (dimension count yields a nonzero vector in
--     S meeting the bottom-(n−k) eigenspace, whose Rayleigh quotient is ≤ λ_k).
-- Both sub-goals drop the outer sSup layer, hence are strictly simpler.
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

-- Courant–Fischer max-min equality, proved by `le_antisymm` over two bounds.
-- h_lower (sub-goal A): eigenvalue k ≤ sSup, via the top-(k+1)-eigenvector test
--   subspace S₀ where every Rayleigh quotient ≥ eigenvalue k.
-- h_upper (sub-goal B): sSup ≤ eigenvalue k, via any (k+1)-dim S meeting the
--   bottom-(n−k)-eigenvector subspace in a nonzero x with Rayleigh ≤ eigenvalue k.
-- Each bound is a standalone theorem re-declaring all binders; both rely on the
-- proved bricks rayleigh_numerator_eigenbasis / subspace_inter_nonzero_of_finrank.
theorem main : ∀ {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n),
    hT.eigenvalues hn k =
      sSup (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
        Module.finrank ℝ S = (k : ℕ) + 1 ∧
        r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
          q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2))  := by
  intro E _ _ _ T hT n hn k
  have h_lower : hT.eigenvalues hn k ≤
      sSup (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
        Module.finrank ℝ S = (k : ℕ) + 1 ∧
        r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
          q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)) :=
    eigenvalue_le_sup_inf_rayleigh hT hn k
  have h_upper : sSup (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
        Module.finrank ℝ S = (k : ℕ) + 1 ∧
        r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
          q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)) ≤ hT.eigenvalues hn k :=
    sup_inf_rayleigh_le_eigenvalue hT hn k
  exact le_antisymm h_lower h_upper

end Library.LinearAlgebra.CourantFischer.CourantFischer
