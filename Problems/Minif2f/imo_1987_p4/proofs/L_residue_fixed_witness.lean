-- σ : Fin 1987 → Fin 1987 with σ(a) = f a % 1987 is an involution (iter_shift slide);
-- since 1987 is odd, σ has a fixed point. Sub 1 = involution property in ℕ form
-- (Builder: iter_shift + Nat.div_add_mod). Sub 2 = pure combinatorial extraction of
-- the fixed point (parity / pairing on Fin 1987), independent of hff.
import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs._strategy_s9685

namespace Problems.Minif2f.imo_1987_p4

def residue_fixed_witness := @Problems.Minif2f.imo_1987_p4.s9685

end Problems.Minif2f.imo_1987_p4
