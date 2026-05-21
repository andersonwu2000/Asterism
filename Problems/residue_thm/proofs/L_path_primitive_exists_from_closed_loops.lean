-- Construct F via path integration: pick a basepoint z₀ ≠ a together with a
-- chooser ψ : ℂ → (ℝ → ℂ) giving, for every z ≠ a, a C¹ path in ℂ \ {a} from
-- z₀ to z (sub-goal `path_chooser_avoiding_singularity`). Define F z to be the
-- path integral of Q along that chosen path. For any test path γ avoiding a,
-- F(γ 1) - F(γ 0) reduces to the difference of integrals over the two chosen
-- paths α := ψ(γ 0), β := ψ(γ 1); the sub-goal `path_diff_eq_connector`
-- packages the closed-loop argument (α · γ · β⁻¹ is a C¹ loop avoiding a, so
-- h_loops kills its integral) that turns that difference into the integral
-- along γ.  Both sub-goals receive the full parent hypothesis package.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10497

namespace Problems.residue_thm

def path_primitive_exists_from_closed_loops := @Problems.residue_thm.s10497

end Problems.residue_thm
