import Library.LinearAlgebra.NormalDiagonalization.Flag
import Library.LinearAlgebra.SchurTriangularization.Triangularization
import Mathlib

open InnerProductSpace
open Library.LinearAlgebra.NormalDiagonalization.Flag
open Library.LinearAlgebra.SchurTriangularization.Triangularization

/-!
# Orthonormal adapted bases for normal diagonalization

This file lifts the Schur triangularization result to an **orthonormal** setting.
Starting from an ordinary Schur-adapted basis (whose initial segments are
`T`-invariant), Gram–Schmidt produces an orthonormal basis that retains the flag
property; a further step encodes the result as a `BlockTriangular` matrix.
-/

namespace Library.LinearAlgebra.NormalDiagonalization.AdaptedBasis

variable {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
  [FiniteDimensional ℂ V] (T : V →ₗ[ℂ] V)

-- Witness committed: `e := gramSchmidtOrthonormalBasis hcard b`, where `b` is the
-- Schur-adapted ordinary basis (Library `adapted_basis_exists`).  The ∃ is discharged
-- here; the two sub-goals are about the *fixed* witness, hence strictly smaller:
--   • `flag_span_eq`  — Gram-Schmidt preserves each initial-segment span, so the
--      orthonormal flag `span (e.toBasis '' Iic j)` equals `span (b '' Iic j)`.
--   • `flag_invariant` — the ordinary flag subspace `span (b '' Iic j)` is T-invariant
--      (immediate from the adapted hypothesis `hb`).
-- Linker: rewrite the flag to `b`'s span, apply T-invariance, then `e.toBasis j` lies in
-- its own initial-segment span by `subset_span`.
/-- There exists an orthonormal basis `e` of `V` (indexed by `Fin (finrank ℂ V)`) such that
for every index `j`, the image `T (e j)` lies in the span of the initial segment
`{e 0, …, e j}`. This is obtained by applying Gram–Schmidt to a Schur-adapted ordinary
basis, which preserves the invariant initial-segment spans. -/
theorem adapted_orthonormal_basis :
    ∃ e : OrthonormalBasis (Fin (Module.finrank ℂ V)) ℂ V,
      ∀ j : Fin (Module.finrank ℂ V),
        T (e.toBasis j) ∈ Submodule.span ℂ (e.toBasis '' Set.Iic j)  := by
  obtain ⟨b, hb⟩ := adapted_basis_exists T
  have hcard : Module.finrank ℂ V = Fintype.card (Fin (Module.finrank ℂ V)) :=
    (Fintype.card_fin _).symm
  refine ⟨gramSchmidtOrthonormalBasis hcard b, fun j => ?_⟩
  rw [flag_span_eq b hcard j]
  apply flag_invariant T b hb j
  rw [← flag_span_eq b hcard j]
  exact Submodule.subset_span (Set.mem_image_of_mem _ (Set.mem_Iic.mpr le_rfl))

-- Triangularization in an orthonormal basis = (Schur ⇒ adapted ordinary basis,
-- then Gram-Schmidt to an orthonormal one preserving the flag) + the Library
-- bookkeeping lemma `block_triangular_of_adapted`.
-- Sub-goal `adapted_orthonormal_basis` packages Schur+Gram-Schmidt into the
-- existence of an orthonormal basis `e` with the adapted (flag) condition; the
-- Library lemma then turns that condition into `BlockTriangular id`. The single
-- sub-goal is strictly simpler: it drops all matrix-entry bookkeeping.
/-- There exists an orthonormal basis `e` of `V` such that the matrix of `T` with respect
to `e` is block-triangular (upper-triangular under the identity ordering). This follows
from `adapted_orthonormal_basis` together with the algebraic fact that the adapted flag
condition implies `BlockTriangular id`. -/
theorem block_triangular_basis :
    ∃ e : OrthonormalBasis (Fin (Module.finrank ℂ V)) ℂ V,
      (LinearMap.toMatrix e.toBasis e.toBasis T).BlockTriangular id  := by
  obtain ⟨e, he⟩ := adapted_orthonormal_basis T
  exact ⟨e, block_triangular_of_adapted T e.toBasis he⟩

end Library.LinearAlgebra.NormalDiagonalization.AdaptedBasis
