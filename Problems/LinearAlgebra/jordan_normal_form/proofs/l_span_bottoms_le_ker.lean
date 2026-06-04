import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- span_bottoms_le_ker: each chain-bottom d⟨t,0⟩ maps to 0 under M (hbot), so the span lies in ker M
theorem span_bottoms_le_ker
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    Submodule.span K (Set.range (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩))
      ≤ LinearMap.ker M := by
  apply Submodule.span_le.mpr
  rintro x ⟨t, rfl⟩
  exact LinearMap.mem_ker.mpr (hbot t.1 ⟨0, t.2⟩ rfl)

end Problems.LinearAlgebra.jordan_normal_form
