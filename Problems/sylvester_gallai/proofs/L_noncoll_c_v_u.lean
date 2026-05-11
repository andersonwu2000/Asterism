import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- noncoll_c_v_u: if u,v lie on line ab and c does not, then c,v,u are not collinear.
-- Key polynomial identity: det(a,b,c)*(v.1-u.1)
--   = (v.1-c.1)*det(a,b,u) + (c.1-u.1)*det(a,b,v) - (b.1-a.1)*det(c,v,u)
-- and the analogous y-version. When all three det=0, the product det(a,b,c)*(vi-ui)=0;
-- since u≠v some coordinate differs, giving det(a,b,c)=0 — contradiction.
theorem noncoll_c_v_u :
    ∀ a b u v c : ℝ × ℝ,
      u ≠ v → Collinear a b u → Collinear a b v → ¬ Collinear a b c →
      ¬ Collinear c v u := by
  intro a b u v c huv hcoll_u hcoll_v hncoll_c hcoll_cvu
  unfold Collinear at *
  apply hncoll_c
  have hx : ((a.1 - c.1) * (b.2 - c.2) - (a.2 - c.2) * (b.1 - c.1)) * (v.1 - u.1) = 0 := by
    linear_combination (v.1 - c.1) * hcoll_u + (c.1 - u.1) * hcoll_v - (b.1 - a.1) * hcoll_cvu
  have hy : ((a.1 - c.1) * (b.2 - c.2) - (a.2 - c.2) * (b.1 - c.1)) * (v.2 - u.2) = 0 := by
    linear_combination (v.2 - c.2) * hcoll_u + (c.2 - u.2) * hcoll_v - (b.2 - a.2) * hcoll_cvu
  have huv' : u.1 ≠ v.1 ∨ u.2 ≠ v.2 := by
    rwa [Ne, Prod.ext_iff, not_and_or] at huv
  have hD : (a.1 - c.1) * (b.2 - c.2) - (a.2 - c.2) * (b.1 - c.1) = 0 := by
    rcases huv' with h | h
    · exact (mul_eq_zero.mp hx).resolve_right (sub_ne_zero.mpr h.symm)
    · exact (mul_eq_zero.mp hy).resolve_right (sub_ne_zero.mpr h.symm)
  linarith

end Problems.sylvester_gallai
