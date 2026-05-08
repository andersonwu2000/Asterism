import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- Direct proof: the convex combination yₜ = (1-t)•(P z) + t•w lies in K by
-- convexity, so the metric projector minimisation gives ‖z - P z‖ ≤ ‖z - yₜ‖.
-- Rewrite z - yₜ = (z - P z) - t • (w - P z) (module identity) and square via
-- `pow_le_pow_left₀` with `norm_nonneg`.
theorem s145 :
    ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
      {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
      ∀ {P : X → X}, IsMetricProjector K P →
      ∀ z : X, ∀ w ∈ K, ∀ t : ℝ, 0 < t → t ≤ 1 →
      ‖z - P z‖^2 ≤ ‖(z - P z) - t • (w - P z)‖^2  := by
  intro X _ _ K _ hConv _ P hP z w hw t ht htle
  have hPz : P z ∈ K := (hP z).1
  have hyt : (1 - t) • (P z) + t • w ∈ K :=
    hConv hPz hw (by linarith) ht.le (by ring)
  have h1 : ‖z - P z‖ ≤ ‖z - ((1 - t) • (P z) + t • w)‖ :=
    (hP z).2 _ hyt
  have h2 : z - ((1 - t) • (P z) + t • w) = (z - P z) - t • (w - P z) := by
    module
  rw [h2] at h1
  exact pow_le_pow_left₀ (norm_nonneg _) h1 2

end Problems.proj_nonexpansive
