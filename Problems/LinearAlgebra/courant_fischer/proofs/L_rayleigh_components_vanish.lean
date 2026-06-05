-- For x in the span of an orthonormal sub-family, the repr-components at
-- indices outside that family vanish — pure orthonormality, independent of T.
-- Reduce the concrete top-(k+1) eigenvector span to the abstract lemma:
-- predicate P j := (j:ℕ) ≤ k, and ¬P i follows from k < i.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11633

namespace Problems.LinearAlgebra.courant_fischer

def rayleigh_components_vanish := @Problems.LinearAlgebra.courant_fischer.s11633

end Problems.LinearAlgebra.courant_fischer
