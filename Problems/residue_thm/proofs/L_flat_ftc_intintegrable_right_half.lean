-- On `Set.Ioo (1/2) 1` the path `γ t = α' 0 + ∫₀ᵗ ...` simplifies (by FTC + h_match)
-- to `β' (2t-1)` and `deriv γ t = 2 · derivWithin β' (Icc 0 1) (2t-1)`, so the original
-- integrand agrees with `Q (β' (2t-1)) * (2 · derivWithin β' (Icc 0 1) (2t-1))` on Ioo
-- (sub-goal `right_half_integrand_eq_on_ioo`). The substituted integrand is interval-
-- integrable on `[1/2, 1]` via continuity (sub-goal `right_half_substituted_intintegrable`).
-- Combinator: `IntervalIntegrable.congr_ae`, using `Ioo_ae_eq_Ioc` to lift the Ioo equality
-- to a.e.-equality on `Ι (1/2) 1 = Ioc (1/2) 1`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10673

namespace Problems.residue_thm

def flat_ftc_intintegrable_right_half := @Problems.residue_thm.s10673

end Problems.residue_thm
