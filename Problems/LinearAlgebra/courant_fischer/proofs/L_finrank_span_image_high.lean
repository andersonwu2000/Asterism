-- Span of an orthonormal-basis subset has finrank = cardinality of the index set.
-- hLI: the restricted family {b i : m ≤ i} is linearly independent (orthonormal ⇒ indep).
-- hcard: there are n − m indices i : Fin n with m ≤ i.
-- Rewrite the image as a range, then `finrank_span_eq_card` turns the goal into the count.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11630

namespace Problems.LinearAlgebra.courant_fischer

def finrank_span_image_high := @Problems.LinearAlgebra.courant_fischer.s11630

end Problems.LinearAlgebra.courant_fischer
