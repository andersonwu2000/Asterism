import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- block_eq_zero: complement-block in range N is zero by disjointness of C and range N
-- entry_kind: Builder
theorem block_eq_zero
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W]
    (N : W →ₗ[K] W) (C : Submodule K W) (hC2 : Disjoint C (LinearMap.range N))
    (m : ℕ) (cb : Module.Basis (Fin m) K C) (a : Fin m → K)
    (hmem : (∑ c : Fin m, a c • (cb c : W)) ∈ LinearMap.range N) :
    (∑ c : Fin m, a c • (cb c : W)) = 0 := by
  have hmemC : (∑ c : Fin m, a c • (cb c : W)) ∈ C :=
    Submodule.sum_mem C (fun c _ => Submodule.smul_mem C _ (cb c).2)
  have hmem2 : (∑ c : Fin m, a c • (cb c : W)) ∈ C ⊓ LinearMap.range N :=
    Submodule.mem_inf.mpr ⟨hmemC, hmem⟩
  have hbot : C ⊓ LinearMap.range N = ⊥ :=
    le_antisymm (disjoint_iff_inf_le.mp hC2) bot_le
  rw [hbot] at hmem2
  exact (Submodule.mem_bot K).mp hmem2

end Problems.LinearAlgebra.jordan_normal_form
