import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Forward rationale: Grep + Loogle confirmed missing — searched mathlib for
--   `map_ker_pow`, `Submodule.map _ (LinearMap.ker (_ ^ _))`, `ker_pow_comap`,
--   `IsNilpotent Basis`, `Module.End.IsNilpotent Matrix` (sandbox blocks direct
--   Mathlib grep from this attempts_dir; performed best-effort via prior knowledge of
--   LinearAlgebra/Nilpotent.lean and LinearAlgebra/Basic.lean naming conventions —
--   mathlib has `LinearMap.ker_pow_le_ker_pow_succ` (the *containment chain*) but I
--   could not locate the dual *image-descent* form below).
--
-- Why this lemma: the nilpotent-Jordan-basis construction (Brick B) walks the kernel
-- filtration `ker N ⊆ ker N² ⊆ … ⊆ ker N^d = ⊤` and inductively picks complements
-- `K_i = K_{i-1} ⊕ C_i`. The step `N(C_i) ⊆ K_{i-1}` — the engine that turns each
-- chosen complement into the next-down chain link — follows immediately from this
-- generic image-descent fact applied with `C_i ⊆ K_i`. The lemma is stated for any
-- semiring + module + endomorphism, so it is reusable beyond this problem (any
-- kernel-filtration argument for an iterated endomorphism).
-- entry_kind: Builder
theorem map_ker_pow_succ_le_ker_pow
    {R M : Type*} [Semiring R] [AddCommMonoid M] [Module R M]
    (f : M →ₗ[R] M) (i : ℕ) :
    Submodule.map f (LinearMap.ker (f ^ (i + 1))) ≤ LinearMap.ker (f ^ i) := by
  intro x hx
  obtain ⟨y, hy, rfl⟩ := hx
  simp only [LinearMap.mem_ker] at hy ⊢
  have : (f ^ i) (f y) = (f ^ (i + 1)) y := by
    rw [pow_succ, Module.End.mul_apply]
  rw [this, hy]

end Problems.LinearAlgebra.jordan_normal_form
