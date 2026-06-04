-- Rewrite 52 ± 6√43 = (3 ± √43)² so (·)^(3/2) becomes a cube; then arithmetic difference.
-- h1, h2: rpow-to-cube rewrites (Builder, rpow algebra on positive bases).
-- h3: pure (3+s)³ − (s−3)³ identity given s²=43 (Builder, nlinarith with Real.sq_sqrt).
import Mathlib
import Problems.Minif2f.aime_1990_p2.Defs
import Problems.Minif2f.aime_1990_p2.proofs._strategy_s537

namespace Problems.Minif2f.aime_1990_p2

def main := @Problems.Minif2f.aime_1990_p2.s537

end Problems.Minif2f.aime_1990_p2
