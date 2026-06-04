import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_jordan_form_add_smul_one
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_nilpotent_restrict_sub_smul

namespace Problems.LinearAlgebra.jordan_normal_form

-- Per-eigenspace Jordan basis via the μ-shift: write S := T.restrict (hinv μ) as
-- N + μ•1 where N := S - μ•1 is nilpotent on the generalized eigenspace, apply hJordNilp
-- to N to get a basis whose Jordan-form matrix has zero diagonal, then shift back by μ•1.
-- Sub-goals: (1) `nilpotent_restrict_sub_smul` — N is nilpotent (deep maxGenEigenspace fact);
-- (2) `jordan_form_add_smul_one` — adding μ•1 to a zero-diagonal Jordan matrix stays Jordan
-- form (off-diagonals unchanged, all diagonals become μ so the block-agreement holds). The
-- closer rewrites (N + μ•1) back to S via `abel`.
theorem s10898
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hJordNilp : ∀ μ : K,
        ∀ (N : (Module.End.maxGenEigenspace T μ : Submodule K V) →ₗ[K]
                (Module.End.maxGenEigenspace T μ : Submodule K V)),
          IsNilpotent N →
          ∃ b : Module.Basis
                  (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V)))
                  K (Module.End.maxGenEigenspace T μ : Submodule K V),
            IsJordanForm (LinearMap.toMatrix b b N) ∧
            ∀ i, (LinearMap.toMatrix b b N) i i = 0)
    (hinv : ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
        T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V)) :
    ∀ μ : K, ∃ b : Module.Basis
          (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))) K
          (Module.End.maxGenEigenspace T μ : Submodule K V),
        IsJordanForm (LinearMap.toMatrix b b (T.restrict (hinv μ)))  := by
  intro μ
  have hnilp : IsNilpotent (T.restrict (hinv μ)
      - μ • (1 : Module.End K (Module.End.maxGenEigenspace T μ : Submodule K V))) :=
    nilpotent_restrict_sub_smul T hinv μ
  obtain ⟨b, hJF, hdiag⟩ := hJordNilp μ _ hnilp
  refine ⟨b, ?_⟩
  have hshift := jordan_form_add_smul_one b _ μ hJF hdiag
  have hsub : T.restrict (hinv μ)
      - μ • (1 : Module.End K (Module.End.maxGenEigenspace T μ : Submodule K V)) + μ • 1
        = T.restrict (hinv μ) := by abel
  rwa [hsub] at hshift

end Problems.LinearAlgebra.jordan_normal_form
