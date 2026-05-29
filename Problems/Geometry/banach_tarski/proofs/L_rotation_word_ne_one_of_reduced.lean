-- Freeness assembly: a reduced word's scaled rotation product cannot be the identity.
-- Each generator is `(1/3) • (unscaled integer matrix)`, so the word product is
-- `(1/3)^n • U` where `n = (toWord w).length ≥ 1` and `U` is the un-normalized product;
-- the proved residue invariant `s11396` gives integers `p q r` with `¬3∣q` and
-- `U.mulVec ![0,1,0] = ![p√2, q, r√2]`. If the product were `1`, the middle coordinate
-- forces `(1/3)^n * q = 1`, i.e. `q = 3^n`, divisible by 3 for `n ≥ 1` — contradicting `¬3∣q`.
-- Sub-goals: `scaled_word_prod` (factor `(1/3)^n` out of the list product, pure induction),
-- `smul_mulvec_middle` (extract the middle component of the scaled vector equation),
-- `three_dvd_of_pow_inv_mul` (the `(1/3)^n*q=1 → 3∣q` arithmetic). `s11396` is cited inline.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11407

namespace Problems.Geometry.banach_tarski

def rotation_word_ne_one_of_reduced := @Problems.Geometry.banach_tarski.s11407

end Problems.Geometry.banach_tarski
