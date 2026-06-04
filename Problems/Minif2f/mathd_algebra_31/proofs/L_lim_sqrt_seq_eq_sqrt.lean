import Mathlib
import Problems.Minif2f.mathd_algebra_31.Defs

namespace Problems.Minif2f.mathd_algebra_31

open scoped Topology

-- lim_sqrt_seq_eq_sqrt: continuity of (NNReal.sqrt ∘ (x + ·)) at 9 composed with h₁
set_option linter.style.longLine false in
-- entry_kind: Builder
theorem lim_sqrt_seq_eq_sqrt (x : NNReal) (u : ℕ → NNReal) (h₀ : ∀ n, u (n + 1) = NNReal.sqrt (x + u n)) (h₁ : Filter.Tendsto u Filter.atTop (𝓝 9)) : Filter.Tendsto (fun n => NNReal.sqrt (x + u n)) Filter.atTop (𝓝 (NNReal.sqrt (x + 9))) := by
  have hcont : ContinuousAt (fun y : NNReal => NNReal.sqrt (x + y)) 9 :=
    (NNReal.continuous_sqrt.comp (continuous_const.add continuous_id)).continuousAt
  simpa [Function.comp] using hcont.tendsto.comp h₁

end Problems.Minif2f.mathd_algebra_31
