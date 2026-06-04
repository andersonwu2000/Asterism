import Mathlib
import Problems.Minif2f.aime_1990_p2.Defs
import Problems.Minif2f.aime_1990_p2.proofs.L_cube_diff_eq_828
import Problems.Minif2f.aime_1990_p2.proofs.L_diff_pow32_eq_cube
import Problems.Minif2f.aime_1990_p2.proofs.L_sum_pow32_eq_cube

namespace Problems.Minif2f.aime_1990_p2

-- Rewrite 52 ± 6√43 = (3 ± √43)² so (·)^(3/2) becomes a cube; then arithmetic difference.
-- h1, h2: rpow-to-cube rewrites (Builder, rpow algebra on positive bases).
-- h3: pure (3+s)³ − (s−3)³ identity given s²=43 (Builder, nlinarith with Real.sq_sqrt).
theorem s537 : (52 + 6 * Real.sqrt 43) ^ ((3 : ℝ) / 2) - (52 - 6 * Real.sqrt 43) ^ ((3 : ℝ) / 2) = 828  := by
  have h1 := sum_pow32_eq_cube
  have h2 := diff_pow32_eq_cube
  have h3 := cube_diff_eq_828
  linarith

end Problems.Minif2f.aime_1990_p2
