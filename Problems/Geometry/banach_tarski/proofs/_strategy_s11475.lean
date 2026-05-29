import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Mazur–Ulam: a 0-fixing isometry equivalence of a real normed space is ℝ-linear.
-- Promote `g` to the linear isometry equivalence `L := g.toRealLinearIsometryEquivOfMapZero hg`,
-- whose `map_smul` gives `L (r•x) = r • L x`; rewrite `⇑L = ⇑g` via the coe lemma. Direct, no sub-goals.
theorem s11475
    (g : E ≃ᵢ E) (hg : g 0 = 0) (r : ℝ) (x : E) :
    g (r • x) = r • g x  := by
  have hmap := (g.toRealLinearIsometryEquivOfMapZero hg).map_smul r x
  rw [g.coe_toRealLinearIsometryEquivOfMapZero hg] at hmap
  exact hmap

end Problems.Geometry.banach_tarski
