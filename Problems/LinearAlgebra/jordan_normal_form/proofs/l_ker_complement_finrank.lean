import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- ker_complement_finrank: finrank(ker N) = finrank(range∩ker) + m by disjoint-sup count
-- Mono disjointness gives Disjoint C (range∩ker); rewrite hsup with hC3 + finrank_bot.


theorem ker_complement_finrank
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (C : Submodule K W) (hC2 : Disjoint C (LinearMap.range N))
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N)
    (m : ℕ) (cb : Module.Basis (Fin m) K C) :
    Module.finrank K (LinearMap.ker N)
      = Module.finrank K (LinearMap.range N ⊓ LinearMap.ker N : Submodule K W) + m := by
  have hdisjoint : Disjoint C (LinearMap.range N ⊓ LinearMap.ker N) :=
    hC2.mono_right inf_le_left
  have hm : Module.finrank K C = m := by
    rw [Module.finrank_eq_card_basis cb, Fintype.card_fin]
  have hsup := Submodule.finrank_sup_add_finrank_inf_eq C
    (LinearMap.range N ⊓ LinearMap.ker N)
  have hbot : (C ⊓ (LinearMap.range N ⊓ LinearMap.ker N) : Submodule K W) = ⊥ :=
    disjoint_iff.mp hdisjoint
  rw [hbot, hC3, finrank_bot K W] at hsup
  omega


end Problems.LinearAlgebra.jordan_normal_form
