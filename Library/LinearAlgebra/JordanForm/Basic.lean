import Library.LinearAlgebra.JordanForm.BlockDiagonal
import Library.LinearAlgebra.JordanForm.Defs
import Library.LinearAlgebra.JordanForm.MatrixOps
import Library.LinearAlgebra.JordanForm.NilpotentBasis
import Mathlib

open Library.LinearAlgebra.JordanForm.BlockDiagonal
open Library.LinearAlgebra.JordanForm.Defs
open Library.LinearAlgebra.JordanForm.MatrixOps
open Library.LinearAlgebra.JordanForm.NilpotentBasis

namespace Library.LinearAlgebra.JordanForm.Basic

-- Direct assembly from two mathlib facts: independence + total span of generalized
-- eigenspaces over algClosed `K`, packaged via the submodule iff for `IsInternal`.
-- No sub-goals needed — leaf-bypass.
theorem max_gen_eigenspace_is_internal
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

-- entry_kind: Builder
-- maxgen_eigenspace_invariant: T maps each maximal generalized eigenspace to itself,
-- via mapsTo_maxGenEigenspace_of_comm with Commute.refl T.
theorem maxgen_eigenspace_invariant
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V) :
    ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
      T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V) := by
  intro μ x hx
  exact Module.End.mapsTo_maxGenEigenspace_of_comm (Commute.refl T) μ hx

theorem nilpotent_restrict_sub_smul
    {K : Type*} [Field K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hinv : ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
        T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V))
    (μ : K) :
    IsNilpotent (T.restrict (hinv μ)
        - μ • (1 : Module.End K (Module.End.maxGenEigenspace T μ : Submodule K V)))  := by
  have hmaps : Set.MapsTo ⇑(T - algebraMap K (Module.End K V) μ)
      (Module.End.maxGenEigenspace T μ : Submodule K V)
      (Module.End.maxGenEigenspace T μ : Submodule K V) := by
    intro x hx
    simp only [LinearMap.sub_apply, Algebra.algebraMap_eq_smul_one,
      LinearMap.smul_apply, Module.End.one_apply, SetLike.mem_coe]
    exact Submodule.sub_mem _ (hinv μ x hx) (Submodule.smul_mem _ _ hx)
  have key := Module.End.isNilpotent_restrict_maxGenEigenspace_sub_algebraMap T μ hmaps
  have heq : T.restrict (hinv μ)
      - μ • (1 : Module.End K (Module.End.maxGenEigenspace T μ : Submodule K V))
      = (T - algebraMap K (Module.End K V) μ).restrict hmaps := by
    ext x
    simp [LinearMap.restrict_apply, LinearMap.sub_apply, Algebra.algebraMap_eq_smul_one]
  rw [heq]; exact key

-- Per-eigenspace Jordan basis via the μ-shift: write S := T.restrict (hinv μ) as
-- N + μ•1 where N := S - μ•1 is nilpotent on the generalized eigenspace, apply hJordNilp
-- to N to get a basis whose Jordan-form matrix has zero diagonal, then shift back by μ•1.
-- Sub-goals: (1) `nilpotent_restrict_sub_smul` — N is nilpotent (deep maxGenEigenspace fact);
-- (2) `jordan_form_add_smul_one` — adding μ•1 to a zero-diagonal Jordan matrix stays Jordan
-- form (off-diagonals unchanged, all diagonals become μ so the block-agreement holds). The
-- closer rewrites (N + μ•1) back to S via `abel`.
theorem restriction_has_jordan_basis
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

-- Assembly (Brick C, step 4): glue per-eigenspace Jordan bases into a global one.
-- `maxgen_eigenspace_invariant` gives T-stability of each generalized eigenspace, so
-- `T.restrict (hinv μ)` is well-typed. `restriction_has_jordan_basis` (consuming hJordNilp
-- via the μ-shift `T - μ•id` nilpotency) yields a Jordan-form basis on each block;
-- `glue_maxgen_jordan_blocks` collects these along `hdec` into a block-diagonal global
-- matrix and reindexes blocks contiguously, which is again Jordan form.
theorem jordan_form_assembly_from_decomposition
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hdec : DirectSum.IsInternal
      (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V)))
    (hJordNilp : ∀ μ : K,
        ∀ (N : (Module.End.maxGenEigenspace T μ : Submodule K V) →ₗ[K]
                (Module.End.maxGenEigenspace T μ : Submodule K V)),
          IsNilpotent N →
          ∃ b : Module.Basis
                  (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V)))
                  K (Module.End.maxGenEigenspace T μ : Submodule K V),
            IsJordanForm (LinearMap.toMatrix b b N) ∧
            ∀ i, (LinearMap.toMatrix b b N) i i = 0) :
    ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
      IsJordanForm (LinearMap.toMatrix b b T)  := by
  have hinv := maxgen_eigenspace_invariant T
  have hblock := restriction_has_jordan_basis T hJordNilp hinv
  exact glue_maxgen_jordan_blocks T hdec hinv hblock

-- Three-brick assembly: cite proved siblings (per Strategist directive).
-- max_gen_eigenspace_is_internal T → DirectSum.IsInternal of generalized eigenspaces.
-- nilpotent_has_jordan_basis → per-block Jordan basis for a nilpotent endomorphism.
-- jordan_form_assembly_from_decomposition → glue per-block bases into a global one.
theorem main : ∀ {K : Type*} [Field K] [IsAlgClosed K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
    IsJordanForm
      (LinearMap.toMatrix b b T)  := by
  intro K _ _ V _ _ _ T
  haveI := Classical.decEq K
  exact jordan_form_assembly_from_decomposition T
    (max_gen_eigenspace_is_internal T)
    (fun _ N hN => nilpotent_has_jordan_basis N hN)

end Library.LinearAlgebra.JordanForm.Basic
