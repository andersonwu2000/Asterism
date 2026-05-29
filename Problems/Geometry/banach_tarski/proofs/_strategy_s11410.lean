import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct list induction: each factor f x = c • g x contributes one c, so the
-- whole product scales by c^len. cons step uses smul_mul_smul_comm to merge the
-- two scalars and pow_succ' (c^(n+1) = c * c^n) to match the accumulated power.
theorem s11410 (c : ℝ) (f g : Fin 2 × Bool → Matrix (Fin 3) (Fin 3) ℝ)
    (h : ∀ x, f x = c • g x) (L : List (Fin 2 × Bool)) :
    (L.map f).prod = c ^ L.length • (L.map g).prod  := by
  induction L with
  | nil => simp
  | cons x tl ih =>
    simp only [List.map_cons, List.prod_cons, List.length_cons, ih, h,
      smul_mul_smul_comm, pow_succ']

end Problems.Geometry.banach_tarski
