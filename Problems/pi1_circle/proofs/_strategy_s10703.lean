import Mathlib
import Problems.pi1_circle.Defs

namespace Problems.pi1_circle

-- Affine (straight-line) homotopy `H(t,x) = lineMap (f x) (g x) t` in ℝ:
-- `ContinuousMap.Homotopy.affine f g` already supplies the underlying `Homotopy`;
-- the relative property at `x ∈ {0,1}` collapses via `Path.segment_same` once
-- `h0`/`h1` rewrite the two endpoints to equal points.
theorem s10703
    (f g : C(unitInterval, ℝ)) (h0 : f 0 = g 0) (h1 : f 1 = g 1) :
    f.HomotopicRel g {0, 1}  := by
  refine ⟨{ toHomotopy := ContinuousMap.Homotopy.affine f g
            prop' := ?_ }⟩
  intro t x hx
  change Path.segment (f x) (g x) t = f x
  rcases hx with hx | hx
  · subst hx
    rw [← h0, Path.segment_same]
    simp
  · rw [Set.mem_singleton_iff] at hx
    subst hx
    rw [← h1, Path.segment_same]
    simp

end Problems.pi1_circle
