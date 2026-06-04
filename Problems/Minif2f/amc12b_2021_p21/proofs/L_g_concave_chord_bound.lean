-- Concavity-chord decomposition.
-- Define g(z) := 2^√2 · log z − 2^z · log √2. Then g(√2) = 0 by direct
-- computation, and g is concave on [√2, 3] (sub-goal `g_concave_on_icc`).
-- The abstract chord lemma `chord_zero_left_endpoint` (any concave f on
-- [a,b] with f(a)=0) yields (z−a)·f(b) ≤ (b−a)·f(z), specializing to
-- exactly the parent statement with f = g, a = √2, b = 3.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9807

namespace Problems.Minif2f.amc12b_2021_p21

def g_concave_chord_bound := @Problems.Minif2f.amc12b_2021_p21.s9807

end Problems.Minif2f.amc12b_2021_p21
