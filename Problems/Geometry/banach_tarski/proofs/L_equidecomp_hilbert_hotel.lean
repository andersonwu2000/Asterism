-- Abstract Hilbert-hotel: set T = ⋃ₙ ρⁿ''D ("hotel"), map f = ρ on T / id off T,
-- inverse g = ρ⁻¹ on T / id off T. f sends A onto A∖D (key set fact: ρ''T = T∖D).
-- f,g are abstracted as parameters with defining equations hf/hf'/hg/hg', so each
-- PartialEquiv law + IsDecompOn is a self-contained Builder sub-goal free of the
-- piecewise case-lambda. The combinator is Equidecomp.mk (PartialEquiv.mk …).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11467

namespace Problems.Geometry.banach_tarski

def equidecomp_hilbert_hotel := @Problems.Geometry.banach_tarski.s11467

end Problems.Geometry.banach_tarski
