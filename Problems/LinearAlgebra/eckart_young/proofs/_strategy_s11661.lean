import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- Direct leaf: `b i` (high eigenvector, `i > k`) is orthogonal to the top-(k+1) span.
-- Show `b i ∈ (span {b (castLE j)})ᗮ` by span-induction: on generators it is the
-- orthonormality of the eigenbasis (`b.orthonormal.2`, indices distinct since `castLE j ≤ k < i`),
-- closed under `+`/`•` via `inner_add_right`/`inner_smul_right`; then `inner_left_of_mem_orthogonal hx`.
theorem s11661 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (x : E) (hx : x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))))
    (i : Fin (Module.finrank 𝕜 E)) (hik : k < (i : ℕ)) :
    inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x = (0 : 𝕜) := by
  set b := T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl with hb
  have horth : b i ∈ (Submodule.span 𝕜 (Set.range (fun j : Fin (k + 1) =>
      b (Fin.castLE hk j))))ᗮ := by
    rw [Submodule.mem_orthogonal']
    intro u hu
    induction hu using Submodule.span_induction with
    | mem y hy =>
        obtain ⟨j, rfl⟩ := hy
        have hne : i ≠ Fin.castLE hk j := by
          intro h
          have hv := congrArg Fin.val h
          simp only [Fin.val_castLE] at hv
          have hj := j.isLt
          omega
        exact b.orthonormal.2 hne
    | zero => simp
    | add y z _ _ hy hz => rw [inner_add_right, hy, hz, add_zero]
    | smul c y _ hy => rw [inner_smul_right, hy, mul_zero]
  exact Submodule.inner_left_of_mem_orthogonal hx horth

end Problems.LinearAlgebra.eckart_young
