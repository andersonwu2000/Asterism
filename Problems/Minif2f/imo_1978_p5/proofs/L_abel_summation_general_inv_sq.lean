-- Abel summation identity for arbitrary `b : ℕ → ℝ` against weights 1/k²,
-- by induction on n. Base case (n=0) collapses both sides to 0; step adds
-- b(n+1)/(n+1)² to LHS while RHS difference simplifies via S_{n+1} = S_n + b(n+1).
import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs._strategy_s9762

namespace Problems.Minif2f.imo_1978_p5

def abel_summation_general_inv_sq := @Problems.Minif2f.imo_1978_p5.s9762

end Problems.Minif2f.imo_1978_p5
