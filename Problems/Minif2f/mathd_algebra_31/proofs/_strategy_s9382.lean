import Mathlib
import Problems.Minif2f.mathd_algebra_31.Defs
import Problems.Minif2f.mathd_algebra_31.proofs.L_lim_sqrt_seq_eq_nine
import Problems.Minif2f.mathd_algebra_31.proofs.L_lim_sqrt_seq_eq_sqrt

namespace Problems.Minif2f.mathd_algebra_31

open scoped Topology

-- Decomposition: limit uniqueness on the sequence `n ↦ NNReal.sqrt (x + u n)`.
-- Sub-goal 1 (`lim_sqrt_seq_eq_nine`): via h₀, this sequence is `u (· + 1)`, which tends to 9
--   from h₁ by shift-invariance of `Tendsto` along `atTop`.
-- Sub-goal 2 (`lim_sqrt_seq_eq_sqrt`): continuity of `NNReal.sqrt` composed with `(x + ·)`,
--   applied pointwise to h₁, gives the limit `NNReal.sqrt (x + 9)`.
-- Both limits must agree by `tendsto_nhds_unique`, yielding `9 = NNReal.sqrt (x + 9)`.
-- Note: `open scoped Topology` is required inside this file for the `𝓝` notation.
set_option linter.style.longLine false in
theorem s9382 : ∀ (x : NNReal) (u : ℕ → NNReal) (h₀ : ∀ n, u (n + 1) = NNReal.sqrt (x + u n)) (h₁ : Filter.Tendsto u Filter.atTop (𝓝 9)), 9 = NNReal.sqrt (x + 9)  := by
  intro x u h₀ h₁
  have h_nine := lim_sqrt_seq_eq_nine x u h₀ h₁
  have h_sqrt := lim_sqrt_seq_eq_sqrt x u h₀ h₁
  exact tendsto_nhds_unique h_nine h_sqrt

end Problems.Minif2f.mathd_algebra_31
