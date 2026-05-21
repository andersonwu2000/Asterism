import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integral_pole_summand_has_deriv_within_ici

namespace Problems.residue_thm

-- Chain rule: d/dt exp(-F(t)) = exp(-F(t)) · (-F'(t)).
-- h_int (FTC): F(t) := ∫₀ᵗ deriv γ s / (γ s - a) ds has derivWithin = deriv γ t / (γ t - a)
-- at t ∈ Ico 0 1 on Ici t. Then .neg negates inside the integrand-pos slot, and
-- HasDerivWithinAt.cexp wraps Complex.exp giving exactly the target sum form.
theorem s10296
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    ∀ t ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun t : ℝ => Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a)))
        (Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a))
          * (-(deriv γ t / (γ t - a))))
        (Set.Ici t) t  := by
  intro t ht
  exact (integral_pole_summand_has_deriv_within_ici
      (U:=U) (T:=T) (γ:=γ) hU hT hγ hmap hclosed a ha t ht).neg.cexp

end Problems.residue_thm
