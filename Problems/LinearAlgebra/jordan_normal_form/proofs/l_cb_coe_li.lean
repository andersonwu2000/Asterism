import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
theorem cb_coe_li
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W]
    (C : Submodule K W) (m : ℕ) (cb : Module.Basis (Fin m) K C) :
    LinearIndependent K (fun c : Fin m => (cb c : W)) := by sorry

end Problems.LinearAlgebra.jordan_normal_form
