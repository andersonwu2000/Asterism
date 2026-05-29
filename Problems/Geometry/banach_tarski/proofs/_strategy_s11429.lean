import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_exists_rotation_shift_disjoint
import Problems.Geometry.banach_tarski.proofs.L_pairwise_disjoint_of_shift_disjoint

namespace Problems.Geometry.banach_tarski

-- Hilbert-hotel absorption split into (1) the geometric existence and (2) a pure
-- group-action reduction.
-- exists_rotation_shift_disjoint: the genuine geometry — a rotation about an axis off D,
--   by an angle dodging the countably many resonant values, sends D off all its forward
--   translates g^n '' D (n ≥ 1).
-- pairwise_disjoint_of_shift_disjoint: disjointness of every forward shift from D forces
--   the full ℕ-indexed family (g^i '' D) to be pairwise disjoint (apply g^{-i}, reduce to
--   one shift). Combining gives the claim.
theorem s11429
    (D : Set E) (hD : D.Countable) :
    ∃ ρ : E ≃ᵢ E, ρ 0 = 0 ∧
      Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))  := by
  obtain ⟨ρ, hρ0, hshift⟩ := exists_rotation_shift_disjoint D hD
  exact ⟨ρ, hρ0, pairwise_disjoint_of_shift_disjoint ρ D hshift⟩

end Problems.Geometry.banach_tarski
