import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_int_eq_winding_residue_via_repr
import Problems.residue_thm.proofs.L_p_cauchy_integral_repr

namespace Problems.residue_thm

-- Decompose ∫_γ P = 2πi · winding · residue P a into two analytical sub-goals:
--   (1) `p_cauchy_integral_repr` — P is its own inner Cauchy integral: for any
--       z ≠ a and ε ∈ (0, dist z a), P z = -(2πi)⁻¹ · ∮_{C(a, ε)} P(w)/(w-z) dw
--       (follows from `inner_principal_part_exists` applied to P on any punctured
--       ball + Liouville-style uniqueness — the difference extends analytically
--       through `a` and decays at infinity, hence vanishes).
--   (2) `path_int_eq_winding_residue_via_repr` — given that Cauchy repr, derive
--       the full parent identity (downstream Builder/Backward bridges ∫_γ P =
--       winding · ∮_{C(a, ε)} P via Fubini + winding-formula, then converts ∮
--       to residue via `residue_eq_circle_integral`).
-- Combinator: feed (1) as the repr hypothesis to (2).
theorem s10454
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t) =
      2 * Real.pi * Complex.I *
        ((Complex.windingNumber γ a : ℂ) * Complex.residue P a)  := by
  have h_repr := p_cauchy_integral_repr hP hP_tendsto
  exact path_int_eq_winding_residue_via_repr hP hP_tendsto h_repr hγ h_avoid hclosed

end Problems.residue_thm
