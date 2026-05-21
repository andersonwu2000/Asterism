-- Decomposition: split t ∈ Ioo 0 1 by whether φ t is in the open interior
-- Ioo 0 1 or hits an endpoint {0, 1} (since hφrange + hφmono only force
-- φ t ∈ Icc 0 1 with φ non-decreasing; interior t may map to a boundary).
--   • Interior case: extract DifferentiableAt γ (φ t) from ContDiffOn-Icc
--     via Icc_mem_nhds (sub-goal `gamma_diff_at_interior`), then the
--     standard chain rule `HasDerivAt.scomp` closes the equation.
--   • Boundary case: dispatch to sub-goal `chain_rule_at_boundary_image`,
--     where deriv φ t = 0 follows from monotonicity collapsing φ to a
--     constant on a one-sided neighborhood and a Lipschitz bound on γ
--     forces deriv (γ ∘ φ) t = 0 as well.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10637

namespace Problems.residue_thm

def chain_rule_compose_reparam_pointwise_ioo := @Problems.residue_thm.s10637

end Problems.residue_thm
