-- Strip the `End`/`FundamentalGroup` wrapping by performing the construction one
-- layer down on `Path.Homotopic.Quotient (1:Circle) 1` (the underlying Hom-set
-- of `FundamentalGroupoid Circle`). The sub-goal asks for W' on the quotient
-- with refl/trans/bijective; the combinator transports those properties through
-- `FundamentalGroup.toPath` (an abbrev; defeq up to `End.one_def`, `End.mul_def`,
-- and `FundamentalGroupoid.comp = Path.Homotopic.Quotient.trans`) and uses
-- `Quotient.ind` to expose path representatives for the multiplicative case.
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10690

namespace Problems.pi1_circle

def winding_int_iso_data := @Problems.pi1_circle.s10690

end Problems.pi1_circle
