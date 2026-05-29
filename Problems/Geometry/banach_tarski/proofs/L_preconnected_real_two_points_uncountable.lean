-- A preconnected T ⊆ ℝ with two distinct points a, b is uncountable.
-- Preconnected ⇒ OrdConnected, so the nondegenerate interval uIcc a b ⊆ T
-- (inlined via hT.ordConnected.uIcc_subset). That interval is uncountable
-- (uicc_uncountable, the only sub-goal). If T were countable so would its
-- subset uIcc a b — contradiction.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11526

namespace Problems.Geometry.banach_tarski

def preconnected_real_two_points_uncountable := @Problems.Geometry.banach_tarski.s11526

end Problems.Geometry.banach_tarski
