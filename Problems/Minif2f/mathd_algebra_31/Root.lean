-- Decomposition: limit uniqueness on the sequence `n ↦ NNReal.sqrt (x + u n)`.
-- Sub-goal 1 (`lim_sqrt_seq_eq_nine`): via h₀, this sequence is `u (· + 1)`, which tends to 9
--   from h₁ by shift-invariance of `Tendsto` along `atTop`.
-- Sub-goal 2 (`lim_sqrt_seq_eq_sqrt`): continuity of `NNReal.sqrt` composed with `(x + ·)`,
--   applied pointwise to h₁, gives the limit `NNReal.sqrt (x + 9)`.
-- Both limits must agree by `tendsto_nhds_unique`, yielding `9 = NNReal.sqrt (x + 9)`.
-- Note: `open scoped Topology` is required inside this file for the `𝓝` notation.
import Mathlib
import Problems.Minif2f.mathd_algebra_31.Defs
import Problems.Minif2f.mathd_algebra_31.proofs._strategy_s9382

namespace Problems.Minif2f.mathd_algebra_31

def main := @Problems.Minif2f.mathd_algebra_31.s9382

end Problems.Minif2f.mathd_algebra_31
