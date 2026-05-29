-- Origin-fixing mirror of build_non_letter0_equidecomp (s11473): the non-letter-0 piece is
-- the trans-composition absorb_empty_word ∘ b_letter_equidecomp.  Each factor is refined to
-- ALSO expose its origin-fixing realizing Finset (absorb: {φ(of 1)⁻¹,1}; b-letter: {1,φ(of 1)},
-- all fixing 0 via hfix0), and a generic origin-fixing trans-glue composes them: the composite
-- Finset = S₂ * S₁ (products of the per-step shifts), each a product of origin-fixers ⇒ fixes 0.
-- Sub-goals: (1) absorb_empty_word_origin_fixing, (2) b_letter_equidecomp_origin_fixing,
-- (3) equidecomp_trans_glue_origin_fixing (abstract).  Combinator: obtain the two factors,
-- glue, thread source/target/IsDecompOn/origin-fixing straight through.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11524

namespace Problems.Geometry.banach_tarski

def build_non_letter0_equidecomp_origin_fixing := @Problems.Geometry.banach_tarski.s11524

end Problems.Geometry.banach_tarski
