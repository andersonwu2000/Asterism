-- In a 1-dim space every endomorphism is a scalar c • id (sub-goal
-- `endo_finrank_one_eq_smul_id`). Then det f = c^finrank · det id = c (finrank=1),
-- and (c•id) x = c • x, closing f x = (det f) • x.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11426

namespace Problems.Geometry.banach_tarski

def endo_eq_det_smul_of_finrank_one := @Problems.Geometry.banach_tarski.s11426

end Problems.Geometry.banach_tarski
