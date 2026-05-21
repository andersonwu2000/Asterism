import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- gamma_avoids_w_on_sphere: γ never hits the ε-sphere because dist(γ t, a) > ε = dist(w, a)
theorem gamma_avoids_w_on_sphere
    {γ : ℝ → ℂ} {a : ℂ} {ε : ℝ}
    (hε_sep : ∀ t ∈ Set.Icc (0 : ℝ) 1, ε < dist (γ t) a) :
    ∀ w ∈ Metric.sphere a ε, ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ w := by
  intro w hw t ht heq
  rw [Metric.mem_sphere] at hw
  have h := hε_sep t ht
  rw [heq] at h
  linarith

end Problems.residue_thm
