-- Per-pole call to `principal_part_extraction_at_singularity` plus a global gluing of the
-- analytic remainder. Three sub-goals:
--  (1) `per_pole_principal_part_data` — for each `a ∈ T`, witness the per-pole principal
--      part `P a` (analytic off `{a}`, tendsto zero at ∞) together with an isolating
--      radius `R a` and a local analytic remainder `h a` on `ball a (R a)` such that
--      `f = h a + P a` on the punctured ball.
--  (2) `global_remainder_glue` — from the per-pole data, glue the analytic remainders into
--      a single `g : ℂ → ℂ` analytic on all of `U`, deliver the pointwise decomposition
--      `f = g + ∑ P a` on `U \ T`, and derive each residue equality
--      `residue (P a) a = residue f a` via additivity of residues across analytic terms.
--  (3) `integral_decomp_from_pointwise` — from the pointwise identity on `U \ T`,
--      analyticity of `g` and each `P a`, and `γ` mapping into `U \ T`, conclude the
--      contour-integral identity by linearity of integration (each integrand is continuous
--      on `Icc 0 1`).
-- Combinator: obtain `(P, R, h, hper)` via (1); obtain `(g, hg, hpw, hres)` via (2);
-- apply (3) to convert `hpw` into the integral identity; package the existential witness.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10453

namespace Problems.residue_thm

def analytic_remainder_principal_part_decomp := @Problems.residue_thm.s10453

end Problems.residue_thm
