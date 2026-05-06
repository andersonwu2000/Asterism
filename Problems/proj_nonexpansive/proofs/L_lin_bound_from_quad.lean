-- lin_bound_from_quad: Divides the quadratic bound `2tc ≤ t²M` by `t > 0` via nlinarith with `t² = t·t` (ring) and `0 < t·t` (mul_pos) hints, giving a degree-2 Positivstellensatz certificate: negating `2c ≤ tM` and multiplying by t contradicts the hypothesis.
--
-- ## Strategy
--
-- Introduce `t`, `ht : 0 < t`, `ht1 : t ≤ 1`. Instantiate the quadratic hypothesis to get `hbound : 2·t·c ≤ t²·M`. Use `ring` to rewrite `t² = t·t`, then `nlinarith [mul_pos ht ht]` finds the contradiction: assuming `2c > tM` and multiplying by `t` yields `2tc > t²M`, contradicting `hbound`.
import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- entry_kind: Builder
theorem lin_bound_from_quad (c M : ℝ) (hM : 0 ≤ M)
    (h : ∀ t : ℝ, 0 < t → t ≤ 1 → 2 * t * c ≤ t ^ 2 * M) :
    ∀ t : ℝ, 0 < t → t ≤ 1 → 2 * c ≤ t * M := by
  intro t ht ht1
  have hbound := h t ht ht1
  have expand : t ^ 2 = t * t := by ring
  nlinarith [mul_pos ht ht]

end Problems.proj_nonexpansive
