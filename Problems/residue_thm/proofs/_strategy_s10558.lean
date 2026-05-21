import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_int_eq_neg_winding_at_w
import Problems.residue_thm.proofs.L_winding_const_on_eps_sphere

namespace Problems.residue_thm

-- For w on the ε-sphere around a (and γ avoiding the closed ε-disk around a):
--   (A) `path_int_eq_neg_winding_at_w` — turn ∫ γ'/(w - γt) into -(2πi)·(windingNumber γ w)
--       via winding_integral_formula at w plus the sign flip 1/(w-γt) = -1/(γt-w).
--   (B) `winding_const_on_eps_sphere` — windingNumber γ w = windingNumber γ a for
--       w on the ε-sphere (winding constancy on the connected ε-disk that γ avoids).
theorem s10558
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_R : ε < R)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    ∀ w ∈ Metric.sphere a ε,
      (∫ t in (0:ℝ)..1, deriv γ t / (w - γ t))
        = -(2 * (Real.pi : ℂ) * Complex.I) * (Complex.windingNumber γ a : ℂ)  := by
  intro w hw
  have hA := path_int_eq_neg_winding_at_w hγ hclosed hε_sep w hw
  have hB := winding_const_on_eps_sphere hγ hclosed hε_pos hε_sep w hw
  rw [hA, hB]


end Problems.residue_thm
