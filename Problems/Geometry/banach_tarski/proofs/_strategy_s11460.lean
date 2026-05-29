import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_collision_forces_cos
import Problems.Geometry.banach_tarski.proofs.L_cos_level_set_countable

namespace Problems.Geometry.banach_tarski

-- Off-axis collision set {t | R0 t p = q} is countable, via a cosine level set.
-- For off-axis p the rotation angle's cosine is pinned: R0 t p = q forces
-- cos t = (p₀q₀ + p₁q₁)/(p₀²+p₁²), a single fixed value (collision_forces_cos:
-- unfold the rotation matrix on components 0,1 and solve the 2×2 system).
-- A cosine level set {t | cos t = c} is countable (cos_level_set_countable:
-- cos is strictly monotone on each [kπ,(k+1)π], so ≤1 root per interval over a
-- countable cover). The collision set is a subset of it, so Set.Countable.mono
-- transports countability back. Both sub-goals are strictly simpler: one is pure
-- matrix algebra, the other a matrix-free analytic fact.
theorem s11460
    (R0 : ℝ → (E ≃ᵢ E))
    (hreal : ∀ (t : ℝ) (x : E),
      R0 t x =
        Matrix.toEuclideanLin
          (!![Real.cos t, -Real.sin t, 0;
              Real.sin t, Real.cos t, 0;
              0, 0, 1] : Matrix (Fin 3) (Fin 3) ℝ) x)
    (p : E) (hp : ¬ (p 0 = 0 ∧ p 1 = 0)) (q : E) :
    {t : ℝ | R0 t p = q}.Countable  := by
  have key := collision_forces_cos R0 hreal p hp q
  have hcos := cos_level_set_countable ((p 0 * q 0 + p 1 * q 1) / (p 0 ^ 2 + p 1 ^ 2))
  exact hcos.mono key

end Problems.Geometry.banach_tarski
