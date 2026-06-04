import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs

namespace Problems.Minif2f.imo_1979_p1

-- denom_prod_pos: each factor (660+j)*(1319-j) is positive for j < 330,
-- so the product over j ∈ range 330 is positive by Finset.prod_pos.
theorem denom_prod_pos :
    0 < ∏ j ∈ Finset.range 330, ((660 + j) * (1319 - j)) := by
  apply Finset.prod_pos
  intro j hj
  apply Nat.mul_pos
  · omega
  · have hj' : j < 330 := Finset.mem_range.mp hj
    omega

end Problems.Minif2f.imo_1979_p1
