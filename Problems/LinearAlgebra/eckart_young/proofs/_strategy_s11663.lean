import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- Direct leaf: x is a finite combination of the first k+1 eigenvectors b(castLE j),
-- and b i (with i > k) is orthogonal to each of them, so ⟨b i, x⟩ vanishes termwise.
-- Expand x via mem_span_range_iff_exists_fun, push inner through the sum/scalar,
-- and kill each ⟨b i, b (castLE j)⟩ by orthonormality since i ≠ castLE j (val j ≤ k < i).
theorem s11663 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (x : E) (hx : x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))))
    (i : Fin (Module.finrank 𝕜 E)) (hi : k < (i : ℕ)) :
    (inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
      (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x : 𝕜) = 0  := by
  set b := T.isSymmetric_adjoint_comp_self.eigenvectorBasis
    (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) with hb
  obtain ⟨c, rfl⟩ := (Submodule.mem_span_range_iff_exists_fun 𝕜).mp hx
  rw [inner_sum]
  apply Finset.sum_eq_zero
  intro j _
  rw [inner_smul_right]
  have hij : i ≠ Fin.castLE hk j := by
    apply Fin.ne_of_val_ne
    simp only [Fin.val_castLE]
    omega
  rw [b.orthonormal.2 hij, mul_zero]

end Problems.LinearAlgebra.eckart_young
