-- Trans-glue of two origin-fixing equidecompositions: witness e := e₁.trans e₂,
-- realizing Finset S := S₂ ⋆ S₁ (Finset.image₂ (·*·)). Source/target come from the
-- PartialEquiv.trans laws; IsDecompOn from per-factor decomp + mul_smul; origin-fixing
-- since (g₂*g₁) 0 = g₂ (g₁ 0) = g₂ 0 = 0. Self-contained leaf.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11529

namespace Problems.Geometry.banach_tarski

def equidecomp_trans_glue_origin_fixing := @Problems.Geometry.banach_tarski.s11529

end Problems.Geometry.banach_tarski
