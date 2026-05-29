import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Forward rationale: Grep + Loogle confirmed missing (keywords searched: "Pairwise
-- Disjoint on pow image", "exists isometry/rotation disjoint orbit countable", "countable
-- absorption Hilbert hotel equidecomp", "Set.Countable uncountable sphere axis avoid").
-- Strategist pre-query already returned 0 hits for the exact shape
-- `(s : Set _) → s.Countable → ∃ g, Pairwise (Disjoint on fun n => (g^n) '' s)`; this
-- sandbox blocks re-running grep/loogle on mathlib, so I rely on that confirmation plus
-- knowledge of mathlib's coverage (no Hilbert-hotel / paradoxical-absorption lemma exists).
--
-- This is the EXISTENCE half of the countable-set absorption (Hilbert-hotel) bridge the
-- brief asks for: given a countable D ⊆ E there is an origin-fixing isometry ρ (a rotation
-- about an axis chosen off D — possible since D is countable but the sphere is uncountable —
-- by an angle avoiding the countably many resonant values that would force ρ^i x = ρ^j y)
-- whose forward powers send D to pairwise-disjoint copies. Requiring `ρ 0 = 0` pins ρ to a
-- genuine rotation: by Mazur–Ulam an origin-fixing isometry of E is linear, hence preserves
-- every centered sphere, so ρ maps S² into S². This existence theorem feeds the
-- equidecomposition `S² \ D ≃ S²` (shift the orbit by one) which lets
-- `rotation_subgroup_paradoxical` lift to a paradoxical decomposition of the full sphere.
-- entry_kind: Backward
theorem exists_rotation_pairwise_disjoint_orbit
    (D : Set E) (hD : D.Countable) :
    ∃ ρ : E ≃ᵢ E, ρ 0 = 0 ∧
      Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D)) := by
  sorry

end Problems.Geometry.banach_tarski
