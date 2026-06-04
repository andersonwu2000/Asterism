import Mathlib
import Problems.Minif2f.algebra_3rootspoly_amdtamctambeqnasqmbpctapcbtdpasqmbpctapcbta.Defs

namespace Problems.Minif2f.algebra_3rootspoly_amdtamctambeqnasqmbpctapcbtdpasqmbpctapcbta

-- Polynomial identity in ℂ; both sides expand to the same monic cubic in a.
-- Closed directly by `ring` after introducing the four universally quantified variables.
theorem s505 : ∀ (b c d a : ℂ), (a - d) * (a - c) * (a - b) = -((a ^ 2 - (b + c) * a + c * b) * d) + (a ^ 2 - (b + c) * a + c * b) * a  := by
  intro b c d a
  ring

end Problems.Minif2f.algebra_3rootspoly_amdtamctambeqnasqmbpctapcbtdpasqmbpctapcbta
