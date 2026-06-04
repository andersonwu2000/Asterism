import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_ker_le_span_bottoms
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_span_bottoms_le_ker

namespace Problems.LinearAlgebra.jordan_normal_form

-- ker M = span of the chain bottoms {d⟨t,0⟩ : 0 < l t}, proved by mutual inclusion.
-- h_ker_le_span: a kernel element has zero coefficients on every j ≥ 1 (those map under
--   M to distinct lower basis vectors d⟨t,j-1⟩ by hshift), so it lies in the bottom span.
-- h_span_le_ker: each generator d⟨t,0⟩ is in ker M directly by hbot. le_antisymm combines.
theorem s10967
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    LinearMap.ker M
      = Submodule.span K (Set.range (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩))  := by
  have h_ker_le_span := ker_le_span_bottoms M d hbot hshift
  have h_span_le_ker := span_bottoms_le_ker M d hbot hshift
  exact le_antisymm h_ker_le_span h_span_le_ker

end Problems.LinearAlgebra.jordan_normal_form
