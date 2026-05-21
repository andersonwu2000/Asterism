import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_gamma_avoids_w_on_sphere
import Problems.residue_thm.proofs.L_path_int_eq_neg_winding_at_pt

namespace Problems.residue_thm

-- For w on the ε-sphere: γ avoids w (triangle inequality from hε_sep),
-- so reduce to a pointwise lemma (∀ z avoided by γ, the integral equals
-- -(2πi)·windingNumber γ z) — one sign flip away from winding_integral_formula.
theorem s10568
    {γ : ℝ → ℂ} {a : ℂ} {ε : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    ∀ w ∈ Metric.sphere a ε,
      (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t))
        = -(2 * (Real.pi : ℂ) * Complex.I) * (Complex.windingNumber γ w : ℂ)  := by
  intro w hw
  have h_avoid_w : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ w :=
    gamma_avoids_w_on_sphere (γ := γ) (a := a) (ε := ε) hε_sep w hw
  exact path_int_eq_neg_winding_at_pt hγ hclosed h_avoid_w

end Problems.residue_thm
