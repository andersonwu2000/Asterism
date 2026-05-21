-- Reduce integrality of ∫ deriv γ / (γ - a) to: exp(∫) = 1.
-- Sub-goal `exp_path_integral_eq_one` is the analytic core (constant-function
-- argument: d/dt [exp(-G(t))·(γ t - a)] = 0 with G the partial integral, hence
-- exp(-G(1))·(γ 1 - a) = exp(0)·(γ 0 - a) = γ 0 - a, and γ 0 = γ 1 ≠ a forces
-- exp(-G(1)) = 1; sign-swap gives exp(G(1)) = 1 in the statement here).
-- Closer: `Complex.exp_eq_one_iff` extracts the integer n with ∫ = n·(2πI);
-- ring re-associates to `2 π I · n` as the conclusion demands.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10300

namespace Problems.residue_thm

def exists_winding_integer := @Problems.residue_thm.s10300

end Problems.residue_thm
