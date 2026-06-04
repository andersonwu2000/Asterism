-- Direct induction on n: base case via h₀; succ step rewrites with h₁ and ih, closed by omega
-- after supplying 2^(k+2) = 2·2^(k+1) and the bound k+2 ≤ 2^(k+1) (inner induction on k).
import Mathlib
import Problems.Minif2f.induction_seq_mul2pnp1.Defs
import Problems.Minif2f.induction_seq_mul2pnp1.proofs._strategy_s626

namespace Problems.Minif2f.induction_seq_mul2pnp1

def main := @Problems.Minif2f.induction_seq_mul2pnp1.s626

end Problems.Minif2f.induction_seq_mul2pnp1
