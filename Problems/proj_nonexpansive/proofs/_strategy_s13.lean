import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_inner_diff_combine

namespace Problems.proj_nonexpansive

-- Apply the variational inequality at both x and y, then close with algebra + linarith.
-- VI at x (test = Py) gives 0 ≤ ⟨Px−x, Py−Px⟩; VI at y (test = Px) gives 0 ≤ ⟨Py−y, Px−Py⟩.
-- The sub-goal inner_diff_combine rewrites their sum as ⟨x−y,Px−Py⟩ − ‖Px−Py‖², so linarith closes.
theorem s13 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} (hconvex : Convex ℝ K) {P : X → X} (hP : IsMetricProjector K P)
    (x y : X) : ‖P x - P y‖ ^ 2 ≤ @inner ℝ _ _ (x - y) (P x - P y)  := by
  have hPy_mem : P y ∈ K := (hP y).1
  have hPx_mem : P x ∈ K := (hP x).1
  have h1 : 0 ≤ @inner ℝ _ _ (P x - x) (P y - P x) :=
    projector_variational_ineq hconvex hP x (P y) hPy_mem
  have h2 : 0 ≤ @inner ℝ _ _ (P y - y) (P x - P y) :=
    projector_variational_ineq hconvex hP y (P x) hPx_mem
  have h3 : @inner ℝ _ _ (x - y) (P x - P y) - ‖P x - P y‖ ^ 2 =
      @inner ℝ _ _ (P x - x) (P y - P x) + @inner ℝ _ _ (P y - y) (P x - P y) :=
    inner_diff_combine x y (P x) (P y)
  linarith

end Problems.proj_nonexpansive
