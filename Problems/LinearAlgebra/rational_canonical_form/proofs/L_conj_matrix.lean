import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs

namespace Problems.LinearAlgebra.rational_canonical_form

-- entry_kind: Builder
-- conj_matrix: conjugation lemma — toMatrix in pulled-back basis equals toMatrix in original
-- basis, using `change` to exploit definitional equalities of Basis.map + intertwining h.
theorem conj_matrix {K : Type*} [Field K] {ι : Type*} [Fintype ι] [DecidableEq ι]
    {V : Type*} [AddCommGroup V] [Module K V]
    {W : Type*} [AddCommGroup W] [Module K W]
    (g : V ≃ₗ[K] W) (c : Module.Basis ι K W) (T : V →ₗ[K] V) (S : W →ₗ[K] W)
    (h : ∀ v : V, g (T v) = S (g v)) :
    LinearMap.toMatrix (c.map g.symm) (c.map g.symm) T = LinearMap.toMatrix c c S := by
  ext i j
  simp only [LinearMap.toMatrix_apply]
  change (c.repr (g (T (g.symm (c j))))) i = (c.repr (S (c j))) i
  rw [h, g.apply_symm_apply]

end Problems.LinearAlgebra.rational_canonical_form
