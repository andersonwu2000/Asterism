import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- finrank_range_eq_sum: finrank of range N equals ∑ l using basis d indexed by Σ t, Fin (l t)
theorem finrank_range_eq_sum
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N)) :
    Module.finrank K (LinearMap.range N) = ∑ t : Fin p, l t := by
  rw [Module.finrank_eq_card_basis d, Fintype.card_sigma]
  simp [Fintype.card_fin]

end Problems.LinearAlgebra.jordan_normal_form
