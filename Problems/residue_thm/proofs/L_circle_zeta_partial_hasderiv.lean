import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- circle_zeta_partial_hasderiv: HasDerivAt for the ζ-integrand g(w)/(w-ζ) via HasDerivAt.div
-- Uses w = circleMap c r θ fixed; w ≠ ζ from r < dist ζ c; chain rule gives
-- d/dζ [g(w)/(w-ζ)] = g(w)/(w-ζ)², then smul by deriv(circleMap) θ.
-- entry_kind: Builder
theorem circle_zeta_partial_hasderiv
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r) :
    ∀ θ : ℝ, ∀ ζ : ℂ, r < dist ζ c →
      HasDerivAt
        (fun ζ' => deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ')))
        (deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ) ^ 2))
        ζ := by
  intro θ ζ hζ
  have hw : circleMap c r θ ≠ ζ := by
    intro heq
    rw [← heq, dist_comm] at hζ
    simp [circleMap] at hζ
    rw [abs_of_pos hr] at hζ
    exact lt_irrefl r hζ
  have hne : circleMap c r θ - ζ ≠ 0 := sub_ne_zero.mpr hw
  have h1 : HasDerivAt (fun _ : ℂ => g (circleMap c r θ)) 0 ζ := hasDerivAt_const ζ _
  have h2 : HasDerivAt (fun ζ' => circleMap c r θ - ζ') (-1) ζ := by
    simpa using (hasDerivAt_id ζ).const_sub (circleMap c r θ)
  have h3 := h1.div h2 hne
  have h4 : (0 * (circleMap c r θ - ζ) - g (circleMap c r θ) * -1) /
      (circleMap c r θ - ζ) ^ 2 = g (circleMap c r θ) / (circleMap c r θ - ζ) ^ 2 := by
    ring
  rw [h4] at h3
  exact h3.const_smul (deriv (circleMap c r) θ)

end Problems.residue_thm
