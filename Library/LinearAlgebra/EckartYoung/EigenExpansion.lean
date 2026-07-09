import Mathlib.Analysis.InnerProductSpace.Adjoint
import Mathlib.Analysis.InnerProductSpace.Spectrum

/-!
# Eigenvalue expansions for symmetric operators

This file establishes formulas expressing inner products and squared norms in terms of
eigenvalue decompositions of symmetric linear maps on finite-dimensional inner product spaces.

## Main statements

- `re_inner_symm_eq_sum_eigenvalues`: for a symmetric operator $T$ on a finite-dimensional
  inner product space of dimension $n$,
  $\operatorname{re}\langle Tx, x\rangle = \sum_{i < n} \lambda_i \|\langle b_i, x\rangle\|^2$,
  where $(b_i)$ and $(\lambda_i)$ are the eigenvectors and eigenvalues of `T`.
- `norm_sq_eq_sum_eigen`: for a linear map `T : E →ₗ[𝕜] F`,
  $\|Tx\|^2 = \sum_i \lambda_i \|\langle b_i, x\rangle\|^2$,
  where $\lambda_i$ and $b_i$ are the eigenvalues and eigenvectors of $T^\dagger \circ T$.

-/

namespace Library.LinearAlgebra.EckartYoung.EigenExpansion

/-- For a symmetric linear map `T` on a finite-dimensional inner product space of dimension `n`,
the real part of $\langle Tx, x\rangle$ equals $\sum_{i < n} \lambda_i \|\langle b_i, x\rangle\|^2$,
where $b_i$ and $\lambda_i$ are given by `LinearMap.IsSymmetric.eigenvectorBasis` and
`LinearMap.IsSymmetric.eigenvalues`. -/
theorem re_inner_symm_eq_sum_eigenvalues {𝕜 : Type*} [RCLike 𝕜] {E : Type*}
    [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    (T : E →ₗ[𝕜] E) (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank 𝕜 E = n) (x : E) :
    RCLike.re (inner 𝕜 (T x) x)
      = ∑ i : Fin n, hT.eigenvalues hn i * ‖inner 𝕜 (hT.eigenvectorBasis hn i) x‖ ^ 2 := by
  classical
  rw [← OrthonormalBasis.sum_inner_mul_inner (hT.eigenvectorBasis hn) (T x) x, map_sum]
  apply Finset.sum_congr rfl
  intro i _
  rw [hT x (hT.eigenvectorBasis hn i), hT.apply_eigenvectorBasis hn i, inner_smul_right,
      ← inner_conj_symm, mul_assoc, RCLike.conj_mul,
      ← RCLike.ofReal_pow, ← RCLike.ofReal_mul, RCLike.ofReal_re]

/-- For a linear map `T : E →ₗ[𝕜] F` between finite-dimensional inner product spaces,
$\|Tx\|^2 = \sum_i \lambda_i \|\langle b_i, x\rangle\|^2$, where $\lambda_i$ and $b_i$ are
the eigenvalues and eigenvectors of the self-adjoint composition $T^\dagger \circ T$.
This follows from `re_inner_symm_eq_sum_eigenvalues` applied to `T.adjoint ∘ₗ T` together
with `norm_sq_eq_re_inner` and `LinearMap.adjoint_inner_left`. -/
theorem norm_sq_eq_sum_eigen {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (x : E) :
    ‖T x‖^2 = ∑ i, (T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
      * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 := by
  rw [norm_sq_eq_re_inner (𝕜 := 𝕜), ← LinearMap.adjoint_inner_left]
  simp only [← LinearMap.comp_apply]
  exact re_inner_symm_eq_sum_eigenvalues (T.adjoint ∘ₗ T) T.isSymmetric_adjoint_comp_self rfl x

end Library.LinearAlgebra.EckartYoung.EigenExpansion
