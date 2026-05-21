-- Direct (leaf) proof. Build `g` pointwise: pick a local extension `g_pole a`
-- at each pole via `choose` on `h_loc`, then set `g z := g_pole z _ z` for
-- `z ∈ T` and `g z := f z - ∑ P a z` elsewhere. Analyticity on `U`: on the
-- open complement `U \ T` the function agrees with `h_F_anal` on a
-- neighborhood; at a pole `a`, `hper`'s separation gives `g = g_pole a _`
-- throughout `Metric.ball a (R a)`, so analyticity transfers via
-- `AnalyticAt.congr`. The equality on `U \ T` is by `dif_neg`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10465

namespace Problems.residue_thm

def analytic_glue_from_local_extensions := @Problems.residue_thm.s10465

end Problems.residue_thm
