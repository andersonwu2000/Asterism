import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_half_sphere_two_distinct
import Problems.Geometry.banach_tarski.proofs.L_preconnected_two_points_uncountable

namespace Problems.Geometry.banach_tarski

-- The radius-1/2 sphere in ℝ³ is uncountable: it is preconnected (dim > 1, via
-- `isConnected_sphere`) and contains two distinct points, and a preconnected set
-- with two distinct points in a metric space is uncountable.
-- Sub-goals: (1) general topology lemma `preconnected_two_points_uncountable`
-- (abstract, no sphere geometry); (2) `half_sphere_two_distinct` (two explicit
-- antipodal points on the radius-1/2 sphere). Preconnectedness is cited inline.
theorem s11521 : ¬ (Metric.sphere (0 : E) (1 / 2)).Countable  := by
  have hrank : (1 : Cardinal) < Module.rank ℝ E := by
    have h3 : Module.rank ℝ E = 3 := by
      rw [← Module.finrank_eq_rank]; simp [E]
    rw [h3]; norm_num
  have hpre : IsPreconnected (Metric.sphere (0 : E) (1 / 2)) :=
    (isConnected_sphere hrank 0 (by norm_num)).isPreconnected
  obtain ⟨p, q, hp, hq, hpq⟩ := half_sphere_two_distinct
  exact preconnected_two_points_uncountable hpre hp hq hpq

end Problems.Geometry.banach_tarski
