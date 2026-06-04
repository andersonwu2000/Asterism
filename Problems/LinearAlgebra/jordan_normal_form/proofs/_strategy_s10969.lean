import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_kernel_coeffs_above_zero
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_repr_supported_bottoms_mem_span

namespace Problems.LinearAlgebra.jordan_normal_form

-- ker M ≤ span of chain bottoms: a kernel element's basis coords vanish above the bottoms.
-- kernel_coeffs_above_zero: for w with M w = 0, every coord d.repr w ⟨t,j⟩ with j ≥ 1 is 0
--   (M lowers d⟨t,j⟩ to the distinct basis vector d⟨t,j-1⟩, so M w = 0 forces those coords to 0).
-- repr_supported_bottoms_mem_span: a w whose coords vanish above j=0 equals Σ over bottoms,
--   hence lies in span {d⟨t,0⟩ : 0 < l t}. Each piece drops the parent's ≤/dynamics coupling.
theorem s10969
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    LinearMap.ker M
      ≤ Submodule.span K (Set.range (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩)) := by
  intro w hw
  rw [LinearMap.mem_ker] at hw
  have h_coeffs := kernel_coeffs_above_zero M d hbot hshift w hw
  exact repr_supported_bottoms_mem_span M d hbot hshift w h_coeffs

end Problems.LinearAlgebra.jordan_normal_form
