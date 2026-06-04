import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_jordan_form_assembly_from_decomposition
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_max_gen_eigenspace_is_internal
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_nilpotent_has_jordan_basis

namespace Problems.LinearAlgebra.jordan_normal_form

-- Three-brick assembly: cite proved siblings (per Strategist directive).
-- max_gen_eigenspace_is_internal T → DirectSum.IsInternal of generalized eigenspaces.
-- nilpotent_has_jordan_basis → per-block Jordan basis for a nilpotent endomorphism.
-- jordan_form_assembly_from_decomposition → glue per-block bases into a global one.
theorem s11022 : ∀ {K : Type*} [Field K] [IsAlgClosed K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
    Problems.LinearAlgebra.jordan_normal_form.IsJordanForm
      (LinearMap.toMatrix b b T)  := by
  intro K _ _ V _ _ _ T
  haveI := Classical.decEq K
  exact jordan_form_assembly_from_decomposition T
    (max_gen_eigenspace_is_internal T)
    (fun _ N hN => nilpotent_has_jordan_basis N hN)

end Problems.LinearAlgebra.jordan_normal_form
