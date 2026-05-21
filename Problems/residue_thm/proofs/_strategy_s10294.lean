import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_exp_neg_integral_has_deriv_within_ici
import Problems.residue_thm.proofs.L_gamma_sub_a_has_deriv_within_ici

namespace Problems.residue_thm

-- Product rule: F(t) = (γ t - a) * exp(-∫ deriv γ / (γ - a)) so F'(t) = f' * g + f * g'.
-- h1 derives γ-a; h2 derives the exp-of-negative-integral via chain rule + FTC;
-- HasDerivWithinAt.mul combines them giving exactly the target sum form.
theorem s10294
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    ∀ t ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun t : ℝ => (γ t - a) * Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a)))
        (deriv γ t * Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a))
         + (γ t - a) * (Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a))
                          * (-(deriv γ t / (γ t - a)))))
        (Set.Ici t) t  := by
  intro t ht
  have h1 := gamma_sub_a_has_deriv_within_ici hU hT hγ hmap hclosed a ha t ht
  have h2 := exp_neg_integral_has_deriv_within_ici hU hT hγ hmap hclosed a ha t ht
  exact h1.mul h2

end Problems.residue_thm
