-- Direct list induction: matrix-product action realizes the foldr.
-- nil: empty product = 1, foldr base = v; simp closes mulVec 1 (embed v) = embed v.
-- cons: prod_cons + mulVec_mulVec peel genMat x off, ih handles the tail,
--   hstep rewrites mulVec (genMat x) (embed _) into embed (step x _) = foldr cons.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11395

namespace Problems.Geometry.banach_tarski

def matrix_prod_mulvec_realizes_foldr := @Problems.Geometry.banach_tarski.s11395

end Problems.Geometry.banach_tarski
