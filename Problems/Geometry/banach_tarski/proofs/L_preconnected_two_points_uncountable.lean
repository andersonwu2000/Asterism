-- Reduce uncountability of a preconnected two-point set to the real-line case
-- via the continuous map x ↦ dist x p: its image is preconnected, contains 0 and
-- dist q p (distinct, since p ≠ q), so the abstract ℝ lemma makes the image
-- uncountable; were S countable the image would be countable — contradiction.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11525

namespace Problems.Geometry.banach_tarski

def preconnected_two_points_uncountable := @Problems.Geometry.banach_tarski.s11525

end Problems.Geometry.banach_tarski
