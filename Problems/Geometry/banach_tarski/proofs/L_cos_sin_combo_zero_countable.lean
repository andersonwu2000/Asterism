-- Amplitude-phase reduction: a·cosφ − b·sinφ = r·cos(φ+ψ) (r≠0), so its zero set is the
-- cos-zero set {(2n+1)π/2} translated by −ψ. Two sub-goals:
--   cos_zero_set_countable      — the cos-zero set is countable (range over ℤ);
--   combo_zero_eq_cos_zero_shift — the parent zero set equals that set shifted by −ψ.
-- Countable image of a countable set closes the parent.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11449

namespace Problems.Geometry.banach_tarski

def cos_sin_combo_zero_countable := @Problems.Geometry.banach_tarski.s11449

end Problems.Geometry.banach_tarski
