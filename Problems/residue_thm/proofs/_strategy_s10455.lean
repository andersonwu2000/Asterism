import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_homotopy_invariance_step_wrapper
import Problems.residue_thm.proofs.L_homotopy_to_constant_simply_connected_open

namespace Problems.residue_thm

-- Smooth-null-homotopy route: in a simply-connected open `U ⊆ ℂ`, the closed C¹
-- loop `γ` admits a C² null-homotopy `H` with `H 0 = γ`, `H 1` constant, and
-- endpoints fixed; apply homotopy invariance of contour integrals to transport
-- the integral from `H 0 = γ` to `H 1` ≡ const, where it vanishes because
-- `deriv (const) = 0`.
--   * `homotopy_to_constant_simply_connected_open` — produces the smooth null-
--     homotopy `H` in `U` (topological core: simply-connectedness gives a
--     continuous null-homotopy, which has to be promoted to C²; bundles
--     analytic + boundary-fixed conditions in one existential).
--   * `homotopy_invariance_step_wrapper` — Builder wrapper that delegates to
--     the proved Forward toolkit `homotopy_invariant_contour_integral` (s10331);
--     isolated so the strategy patch only cites local sub-goal slugs (the
--     framework auto-imports the Forward alias inside the wrapper's L_*.lean).
-- Combinator: destructure the homotopy, invoke the wrapper to get
-- `∫g(H 0 t)·deriv (H 0) t = ∫g(H 1 t)·deriv (H 1) t`, rewrite `H 0 = γ` and
-- `H 1 ≡ const`, then `simp` closes via `deriv_const`.
theorem s10455
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0  := by
  obtain ⟨H, hC2, hmapsH, hh0, hh1, hinit, hterm⟩ :=
    homotopy_to_constant_simply_connected_open hU hSC hγ hmaps hclosed
  have h_eq :
      (∫ t in (0:ℝ)..1, g (H 0 t) * deriv (H 0) t) =
        (∫ t in (0:ℝ)..1, g (H 1 t) * deriv (H 1) t) :=
    homotopy_invariance_step_wrapper hU hg hC2 hmapsH hh0 hh1
  rw [hinit, hterm] at h_eq
  rw [h_eq]
  simp

end Problems.residue_thm
