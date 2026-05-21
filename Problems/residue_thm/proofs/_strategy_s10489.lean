import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_primitive_exists_from_closed_loops
import Problems.residue_thm.proofs.L_path_primitive_imp_hasderivat

namespace Problems.residue_thm

-- Morera-style construction of a primitive on ℂ \ {a} from closed-loop-zero.
-- (S1) Path-integral form of F: build F : ℂ → ℂ such that for any C¹ path γ in
--      ℂ \ {a}, F(γ 1) - F(γ 0) = ∫₀¹ Q(γ t) · γ' dt. Uses h_loops via path
--      concatenation/reverse to establish path-independence.
-- (S2) Path-integral equation ⇒ HasDerivAt: for z ≠ a, the straight-line
--      segment γ(t) = z + t·h (with |h| < dist(z,a)) gives F(z+h) - F(z) ≈
--      Q(z)·h via continuity of Q at z, yielding HasDerivAt F (Q z) z.
theorem s10489
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0) :
    ∃ F : ℂ → ℂ, ∀ z ∈ Set.univ \ ({a} : Set ℂ),
      HasDerivAt F (Q z) z  := by
  have h_pathF := path_primitive_exists_from_closed_loops hQ_an h_loops
  obtain ⟨F, hF⟩ := h_pathF
  exact ⟨F, path_primitive_imp_hasderivat hQ_an h_loops F hF⟩

end Problems.residue_thm
