import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Builder
-- ray_param_norm_sq_alg_identity: algebraic identity for the ray parameter t = (√(a²+b(1-c))-a)/b
-- after field_simp the √ terms cancel via (√D)²=D; nlinarith closes using hsq
theorem ray_param_norm_sq_alg_identity
    (a b c : ℝ) (hb : 0 < b) (hc : c ≤ 1) :
    c + 2 * ((Real.sqrt (a^2 + b * (1 - c)) - a) / b) * a +
    ((Real.sqrt (a^2 + b * (1 - c)) - a) / b)^2 * b = 1 := by
  have harg : 0 ≤ a ^ 2 + b * (1 - c) := by nlinarith [sq_nonneg a]
  have hsq : Real.sqrt (a ^ 2 + b * (1 - c)) ^ 2 = a ^ 2 + b * (1 - c) := Real.sq_sqrt harg
  have hb' : b ≠ 0 := hb.ne'
  have hb2 : b ^ 2 ≠ 0 := pow_ne_zero 2 hb'
  set s := Real.sqrt (a ^ 2 + b * (1 - c)) with hs_def
  field_simp [hb']
  nlinarith [hsq, sq_nonneg s, sq_nonneg a, sq_nonneg (s - a),
             mul_comm s a, mul_self_nonneg (s - a)]

end Problems.Topology.brouwer_fixed_point
