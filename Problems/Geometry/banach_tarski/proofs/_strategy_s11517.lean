import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Closed form for the origin-orbit of the conjugated rotation ρ x = R(x-c)+c.
-- Induction on n: base 0 is `c - c = 0`; the step rewrites ρ^(k+1) = ρ ∘ ρ^k,
-- applies the inductive hypothesis and the defining equation hρ, uses linearity
-- of R (map_sub) and R^(k+1) = R ∘ R^k, then closes by abelian-group algebra.
set_option maxHeartbeats 0 in
-- the (ρ^n : E ≃ᵢ E) application on EuclideanSpace ℝ (Fin 3) blows past the
-- default 200k heartbeat whnf limit; lift it.
theorem s11517 (ρ : E ≃ᵢ E) (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hρ : ∀ x : E, ρ x = R (x - c) + c) :
    ∀ n : ℕ, (ρ ^ n) 0 = c - (R ^ n) c  := by
  intro n
  induction n with
  | zero => simp
  | succ k ih =>
    rw [pow_succ', IsometryEquiv.coe_mul, Function.comp_apply, ih, hρ,
      pow_succ', LinearIsometryEquiv.coe_mul, Function.comp_apply]
    simp
    abel



end Problems.Geometry.banach_tarski
