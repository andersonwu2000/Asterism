-- Reduce to a single continuity-only sub-goal. Since `g` is analytic on the
-- open set `U`, it is continuous on `U` (`AnalyticOn.continuousOn`), and `γ`
-- maps `Icc 0 1` into `U \ T ⊆ U`. The remaining work — that
-- `(g ∘ γ) * γ'` is interval-integrable on `0..1` whenever `g` is
-- ContinuousOn `U` and `γ` is `ContDiffOn ℝ 1 γ (Icc 0 1)` mapping into `U` —
-- is the abstracted Builder sub-goal `intvl_integrable_continuous_circ_c1`
-- (no antiderivative is needed: the proof goes through
-- `ContinuousOn.intervalIntegrable_of_Icc` on the `derivWithin` version and
-- `congr_ae` to switch back to `deriv γ`, à la the proved sibling
-- `interval_integrable_integrand`).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10460

namespace Problems.residue_thm

def g_along_path_intvl_integrable := @Problems.residue_thm.s10460

end Problems.residue_thm
