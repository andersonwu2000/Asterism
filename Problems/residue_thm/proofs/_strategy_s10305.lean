import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_differentiable_integral_path

namespace Problems.residue_thm

-- Split `exp(-G(s))` as `exp ∘ (-) ∘ G` where `G(s) := ∫₀ˢ deriv γ /(γ-a)`.
-- Sub-goal: differentiability of `G` (FTC + continuity of the integrand);
-- closer: `.neg` then `DifferentiableOn.cexp` since `Complex.exp` is entire.
theorem s10305
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    DifferentiableOn ℝ
      (fun s => Complex.exp (-(∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))))
      (Set.Icc (0:ℝ) 1)  := by
  have h_int := differentiable_integral_path hγ hclosed havoid
  exact (h_int.neg).cexp

end Problems.residue_thm
