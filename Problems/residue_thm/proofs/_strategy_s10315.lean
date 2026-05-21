import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_residue_eq_circle_integral
import Problems.residue_thm.proofs.L_cycle_decomposition_into_loops

namespace Problems.residue_thm

-- Apply the homological cycle decomposition: for closed C¹ γ in U \ T with U
-- simply-connected and f analytic on U \ T, choose per-pole analytic radii r a
-- and inner radii ρ a < r a; the line integral equals the winding-weighted sum
-- of small loops ∮ C(a, ρ a) f. Convert each loop into 2πi · residue via the
-- proved bridge `residue_eq_circle_integral` (R := r a, r := ρ a), then
-- field_simp/ring reassembles the 2πi factor.
theorem s10315 : ∀ {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ},
  IsOpen U → SimplyConnectedSpace ↥U →
  (∀ a ∈ T, a ∈ U) →
  AnalyticOn ℂ f (U \ ↑T) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T) →
  γ 0 = γ 1 →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 2 * Real.pi * Complex.I *
    ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * Complex.residue f a  := by
  intro U T f γ hU hsc hT hf hγ hmaps hclosed
  have h_decomp := cycle_decomposition_into_loops hU hsc hT hf hγ hmaps hclosed
  obtain ⟨r, ρ, hρ_pos, hρ_lt_r, hr_an, h_eq⟩ := h_decomp
  rw [h_eq, Finset.mul_sum]
  refine Finset.sum_congr rfl ?_
  intro a ha
  have h_2pi_ne : (2 * Real.pi * Complex.I : ℂ) ≠ 0 := by
    have hπ : (Real.pi : ℂ) ≠ 0 := by exact_mod_cast Real.pi_ne_zero
    have hI : Complex.I ≠ 0 := Complex.I_ne_zero
    exact mul_ne_zero (mul_ne_zero two_ne_zero hπ) hI
  have h_res : (2 * Real.pi * Complex.I) * Complex.residue f a =
      ∮ z in C(a, ρ a), f z := by
    rw [residue_eq_circle_integral (hr_an a ha) (hρ_pos a ha) (hρ_lt_r a ha), one_div]
    rw [← mul_assoc, mul_inv_cancel₀ h_2pi_ne, one_mul]
  linear_combination -((Complex.windingNumber γ a : ℂ)) * h_res

end Problems.residue_thm
