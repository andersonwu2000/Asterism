-- Direct proof (leaf-bypass): a cosine level set {t | cos t = c} is countable.
-- Case-split on ∃ t₀, cos t₀ = c. If none, the set is empty. Otherwise
-- `Real.cos_eq_cos_iff` shows every solution t equals 2kπ ± t₀ for some k : ℤ,
-- so the set sits inside the union of two ℤ-indexed ranges (countable), and
-- `Set.Countable.mono` transports countability back.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11466

namespace Problems.Geometry.banach_tarski

def cos_level_set_countable := @Problems.Geometry.banach_tarski.s11466

end Problems.Geometry.banach_tarski
