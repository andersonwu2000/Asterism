import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Library.LinearAlgebra.SchurTriangularization.Triangularization
import Problems.LinearAlgebra.normal_diagonalization.proofs.L_flag_invariant
import Problems.LinearAlgebra.normal_diagonalization.proofs.L_flag_span_eq

namespace Problems.LinearAlgebra.normal_diagonalization

open Library.LinearAlgebra.SchurTriangularization.Triangularization
open InnerProductSpace

-- Witness committed: `e := gramSchmidtOrthonormalBasis hcard b`, where `b` is the
-- Schur-adapted ordinary basis (Library `adapted_basis_exists`).  The ∃ is discharged
-- here; the two sub-goals are about the *fixed* witness, hence strictly smaller:
--   • `flag_span_eq`  — Gram-Schmidt preserves each initial-segment span, so the
--      orthonormal flag `span (e.toBasis '' Iic j)` equals `span (b '' Iic j)`.
--   • `flag_invariant` — the ordinary flag subspace `span (b '' Iic j)` is T-invariant
--      (immediate from the adapted hypothesis `hb`).
-- Linker: rewrite the flag to `b`'s span, apply T-invariance, then `e.toBasis j` lies in
-- its own initial-segment span by `subset_span`.
theorem s11544 {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
    [FiniteDimensional ℂ V] (T : V →ₗ[ℂ] V) :
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

end Problems.LinearAlgebra.normal_diagonalization
