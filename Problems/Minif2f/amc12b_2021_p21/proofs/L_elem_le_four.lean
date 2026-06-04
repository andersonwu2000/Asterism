-- Abstract away the Finset membership wrapper: the real content
-- is a pointwise bound for any positive real satisfying the
-- equation x^(2^√2) = √2^(2^x). Unpack `x ∈ S` via the spec and
-- apply the pointwise bound.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9673

namespace Problems.Minif2f.amc12b_2021_p21

def elem_le_four := @Problems.Minif2f.amc12b_2021_p21.s9673

end Problems.Minif2f.amc12b_2021_p21
