import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem residue_global_principal_part_decomp
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T)) :
    ∃ (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ),
      AnalyticOn ℂ g U ∧
      (∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a})) ∧
      (∀ a ∈ T, Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0)) ∧
      (∀ a ∈ T, Complex.residue (P a) a = Complex.residue f a) ∧
      ∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z := by sorry

end Problems.residue_thm
