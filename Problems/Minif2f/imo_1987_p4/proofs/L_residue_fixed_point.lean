-- Reduce to finding a residue fixed point in Fin 1987: some a < 1987 with f a ≡ a (mod 1987).
-- Given such a, set n = a and k = f a / 1987; then Nat.div_add_mod gives f a = 1987 * k + a,
-- and a < 1987 with f a % 1987 = a forces f a = a + 1987 * k. The residue witness sub-goal
-- carries the involution-on-odd-set argument (1987 odd ⇒ φ : Fin 1987 → Fin 1987 with φ∘φ=id
-- has a fixed point), while the closer here is mechanical Nat.div_add_mod + omega.
import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs._strategy_s9644

namespace Problems.Minif2f.imo_1987_p4

def residue_fixed_point := @Problems.Minif2f.imo_1987_p4.s9644

end Problems.Minif2f.imo_1987_p4
