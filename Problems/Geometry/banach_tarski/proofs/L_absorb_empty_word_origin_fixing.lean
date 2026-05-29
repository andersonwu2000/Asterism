-- Origin-fixing mirror of absorb_empty_word (s11479): same Hilbert-hotel piecewise
-- map f (ρ := φ(of 1)⁻¹ on the orbit tower T, id off T) realizing source ≃ source\D,
-- but now ALSO expose the realizing Finset {ρ,1} and prove every member fixes 0.
-- The four PartialEquiv laws + the tower/disjoint/shift facts are the proved Hilbert
-- bricks (cited inline); the ONLY new sub-goal is is_decomp_hilbert_origin_fixing, which
-- packages the {ρ,1} witness together with ρ 0 = 0 (and 1 0 = 0).  ρ 0 = 0 holds
-- because ρ = φ((of 1)⁻¹) and hfix0 fixes the origin for every φ-image.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11527

namespace Problems.Geometry.banach_tarski

def absorb_empty_word_origin_fixing := @Problems.Geometry.banach_tarski.s11527

end Problems.Geometry.banach_tarski
