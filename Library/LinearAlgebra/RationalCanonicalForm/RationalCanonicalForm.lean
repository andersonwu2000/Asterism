import Library.LinearAlgebra.InvariantFactor.InvariantFactorDecomposition
import Library.LinearAlgebra.RationalCanonicalForm.CompanionMatrix
import Library.LinearAlgebra.RationalCanonicalForm.DirectSumDecomp
import Mathlib.Algebra.DirectSum.Module
import Mathlib.Algebra.Group.Units.Defs
import Mathlib.Algebra.Module.LinearMap.Basic
import Mathlib.Algebra.Polynomial.Basic
import Mathlib.Algebra.Polynomial.Degree.Defs
import Mathlib.Algebra.Polynomial.Module.AEval
import Mathlib.Data.Matrix.Block
import Mathlib.LinearAlgebra.Basis.Basic
import Mathlib.LinearAlgebra.BilinearMap
import Mathlib.LinearAlgebra.DirectSum.Basis
import Mathlib.LinearAlgebra.FiniteDimensional.Defs
import Mathlib.LinearAlgebra.Matrix.ToLin
import Mathlib.LinearAlgebra.Quotient.Basic
import Mathlib.LinearAlgebra.Span.Basic
import Mathlib.RingTheory.AdjoinRoot

/-!
# Rational Canonical Form

This file assembles the rational canonical form theorem: every linear endomorphism
`T : V →ₗ[K] V` of a finite-dimensional `K`-vector space admits a basis with respect
to which the matrix of `T` is block-diagonal with companion matrices as the diagonal
blocks, where the blocks correspond to the invariant factors of `T`.

## Main statements

- `block_assembly`: given an invariant-factor decomposition `e`, constructs a `K`-basis
  making `T` block-diagonal with "multiply by root" operator blocks.
- `companion_block_basis`: identifies each "multiply by root" block with the companion
  matrix of the corresponding invariant factor.
- `rational_canonical_form`: the full rational canonical form theorem, combining invariant
  factor existence with `companion_block_basis`.
-/

open Library.LinearAlgebra.RationalCanonicalForm.CompanionMatrix
open Library.LinearAlgebra.RationalCanonicalForm.DirectSumDecomp

namespace Library.LinearAlgebra.RationalCanonicalForm.RationalCanonicalForm

variable {K : Type*} [Field K] {V : Type*} [AddCommGroup V] [Module K V]
    [FiniteDimensional K V]

/-- Given a `K[X]`-linear equivalence `e` witnessing the invariant factor decomposition of `T`,
constructs a `K`-basis `b` of `V` such that the matrix of `T` with respect to `b` is
block-diagonal, with the `i`-th block being the matrix of multiplication by
`AdjoinRoot.root (f i)` in the power basis of `K[X] / (f i)`. -/
theorem block_assembly (T : V →ₗ[K] V) {r : ℕ} (f : Fin r → Polynomial K)
    (hmonic : ∀ i, (f i).Monic)
    (e : Module.AEval' T ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i})) :
    ∃ b : Module.Basis (Σ i : Fin r, Fin (f i).natDegree) K V,
      LinearMap.toMatrix b b T
        = Matrix.blockDiagonal' (fun i ↦
            LinearMap.toMatrix (AdjoinRoot.powerBasis' (hmonic i)).basis
              (AdjoinRoot.powerBasis' (hmonic i)).basis
              (LinearMap.mulLeft K (AdjoinRoot.root (f i)))) := by
  classical
  set g : V ≃ₗ[K]
      DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i}) :=
    (Module.AEval'.of T).trans (e.restrictScalars K) with hg
  set c : Module.Basis (Σ i : Fin r, Fin (f i).natDegree) K
      (DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i})) :=
    DFinsupp.basis (fun i ↦ (AdjoinRoot.powerBasis' (hmonic i)).basis) with hc
  set S : DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i}) →ₗ[K]
      DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i}) :=
    (LinearMap.lsmul (Polynomial K) _ Polynomial.X).restrictScalars K with hS
  refine ⟨c.map g.symm, ?_⟩
  have hint : ∀ v : V, g (T v) = S (g v) := by
    rw [hg, hS]; exact intertwine_x T f e
  have hconj : LinearMap.toMatrix (c.map g.symm) (c.map g.symm) T
      = LinearMap.toMatrix c c S := conj_matrix g c T S hint
  have hblock : LinearMap.toMatrix c c S
      = Matrix.blockDiagonal' (fun i ↦
          LinearMap.toMatrix (AdjoinRoot.powerBasis' (hmonic i)).basis
            (AdjoinRoot.powerBasis' (hmonic i)).basis
            (LinearMap.mulLeft K (AdjoinRoot.root (f i)))) := by
    rw [hc, hS]; exact block_diag f hmonic
  rw [hconj, hblock]

/-- Given an invariant factor decomposition `e` of `T`, constructs a basis `b` such that
the matrix of `T` with respect to `b` is block-diagonal with `companionMatrix (f i)` as the
`i`-th diagonal block. -/
theorem companion_block_basis (T : V →ₗ[K] V) {r : ℕ} (f : Fin r → Polynomial K)
    (hmonic : ∀ i, (f i).Monic)
    (e : Module.AEval' T ≃ₗ[Polynomial K]
        DirectSum (Fin r) (fun i ↦ Polynomial K ⧸ Submodule.span (Polynomial K) {f i})) :
    ∃ b : Module.Basis (Σ i : Fin r, Fin (f i).natDegree) K V,
      LinearMap.toMatrix b b T
        = Matrix.blockDiagonal' (fun i ↦ companionMatrix (f i)) := by
  obtain ⟨b, hb⟩ := block_assembly T f hmonic e
  refine ⟨b, ?_⟩
  rw [hb]
  congr 1
  funext i
  exact block_companion (hmonic i)

/-- **Rational canonical form**: every linear endomorphism of a finite-dimensional vector space
over a field admits a basis in which its matrix is block-diagonal with the companion matrices of
the invariant factors as the diagonal blocks. The invariant factors are monic, non-unit, and
satisfy the divisibility chain $f_0 \mid f_1 \mid \cdots \mid f_{r-1}$. -/
theorem rational_canonical_form (T : V →ₗ[K] V) :
    ∃ (r : ℕ) (f : Fin r → Polynomial K),
      (∀ i, (f i).Monic) ∧
      (∀ i, ¬ IsUnit (f i)) ∧
      (∀ i j, i ≤ j → f i ∣ f j) ∧
      ∃ b : Module.Basis (Σ i : Fin r, Fin (f i).natDegree) K V,
        LinearMap.toMatrix b b T
          = Matrix.blockDiagonal' (fun i ↦ companionMatrix (f i)) := by
  obtain ⟨r, f, hmonic, hnonunit, hdvd, ⟨e⟩⟩ :=
    Library.LinearAlgebra.InvariantFactor.InvariantFactorDecomposition.main T
  exact ⟨r, f, hmonic, hnonunit, hdvd, companion_block_basis T f hmonic e⟩

end Library.LinearAlgebra.RationalCanonicalForm.RationalCanonicalForm
