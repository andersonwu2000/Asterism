import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct assembly from two mathlib facts: independence + total span of generalized
-- eigenspaces over algClosed `K`, packaged via the submodule iff for `IsInternal`.
-- No sub-goals needed — leaf-bypass.
theorem s10887
    {K V : Type*} [Field K] [IsAlgClosed K] [DecidableEq K]
    [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V) :
    DirectSum.IsInternal
      (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V)) := by
  have h_indep := Module.End.independent_maxGenEigenspace T
  have h_iSup_top := Module.End.iSup_maxGenEigenspace_eq_top T
  exact (DirectSum.isInternal_submodule_iff_iSupIndep_and_iSup_eq_top
    (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V))).mpr
    ⟨h_indep, h_iSup_top⟩

end Problems.LinearAlgebra.jordan_normal_form
