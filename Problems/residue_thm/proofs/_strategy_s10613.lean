import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_n_continuous_on_ball_from_f

namespace Problems.residue_thm

-- Locally-constant principle for integer-valued continuous maps on a connected ball.
-- The ball `Metric.ball z r` in ℂ is preconnected (it is convex). Combined with
-- `ContinuousOn n` (where ℤ carries the discrete topology), `IsPreconnected.constant`
-- forces `n w = n z` for every `w` in the ball.
-- (A) `n_continuous_on_ball_from_f` (Builder): the integer label is continuous on
--     the ball because `(n w : ℂ) = f w / (2πi)` on the ball and `Int.cast : ℤ → ℂ`
--     is a topological embedding, so continuity of `f` lifts back to continuity of `n`.
theorem s10613
    {z : ℂ} {r : ℝ}
    (hr : 0 < r)
    {f : ℂ → ℂ}
    (hf : ContinuousOn f (Metric.ball z r))
    {n : ℂ → ℤ}
    (hfn : ∀ w ∈ Metric.ball z r,
              f w = 2 * Real.pi * Complex.I * (n w : ℂ)) :
    ∀ w ∈ Metric.ball z r, n w = n z  := by
  intro w hw
  have hball_pc : IsPreconnected (Metric.ball z r) := (convex_ball z r).isPreconnected
  have hn_cts : ContinuousOn n (Metric.ball z r) :=
    n_continuous_on_ball_from_f hr hf hfn
  exact hball_pc.constant hn_cts hw (Metric.mem_ball_self hr)

end Problems.residue_thm
