import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs._strategy_s11589

namespace Problems.LinearAlgebra.rational_canonical_form

-- block_companion: toMatrix of mulLeft-root in powerBasis' equals companionMatrix;
-- direct application of the already-proved s11589 theorem (variable rename only).
theorem block_companion {K : Type*} [Field K] {g : Polynomial K} (hg : g.Monic) :
    LinearMap.toMatrix (AdjoinRoot.powerBasis' hg).basis (AdjoinRoot.powerBasis' hg).basis
        (LinearMap.mulLeft K (AdjoinRoot.root g))
      = companionMatrix g := s11589 hg

end Problems.LinearAlgebra.rational_canonical_form

