import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

theorem pushforward_inr_zero
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W]
    (N : W →ₗ[K] W)
    (C : Submodule K W) (hC1 : C ≤ LinearMap.ker N)
    (p : ℕ) (l : Fin p → ℕ) (m : ℕ) (cb : Module.Basis (Fin m) K C)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W)) :
    ∀ c : Fin m, N (v ⟨Sum.inr c, (0 : Fin 1)⟩) = 0 := by aesop
end Problems.LinearAlgebra.jordan_normal_form
