import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_free_so3_embedding
import Problems.Geometry.banach_tarski.proofs.L_exists_not_fixed_in_uncountable_sphere
import Problems.Geometry.banach_tarski.proofs.L_fixed_set_half_sphere_finite
import Problems.Geometry.banach_tarski.proofs.L_half_sphere_uncountable
import Problems.Geometry.banach_tarski.proofs.L_of_pow_ne_one

namespace Problems.Geometry.banach_tarski

-- Take R := ψ (of 0), a single free generator of the proved SO(3) embedding ψ
-- (free_so3_embedding): an infinite-order det-1 rotation. For each n ≥ 1, R^n = ψ((of 0)^n)
-- with (of 0)^n ≠ 1, so R^n is a non-trivial det-1 isometry whose fixed set on the radius-1/2
-- sphere is finite (fixed_set_half_sphere_finite bridges rotation_fixed_set_on_sphere_finite
-- to radius 1/2). The union over n ≥ 1 of these fixed sets is countable, but the sphere is
-- uncountable (half_sphere_uncountable), so a point c with ‖c‖ = 1/2 escapes every power
-- (exists_not_fixed_in_uncountable_sphere). Sub-goals: of_pow_ne_one (generator has infinite
-- order), the radius-1/2 finiteness bridge, sphere uncountability, and the set-theoretic
-- "uncountable minus countably-many finite sets is nonempty" combine.
theorem s11514 :
    ∃ (R : E ≃ₗᵢ[ℝ] E) (c : E),
      ‖c‖ ≤ 1 / 2 ∧ ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c  := by
  obtain ⟨ψ, hinj, hprop⟩ := free_so3_embedding
  have hfin : ∀ n : ℕ, 1 ≤ n →
      {x ∈ Metric.sphere (0 : E) (1 / 2) | ((ψ (FreeGroup.of 0)) ^ n) x = x}.Finite := by
    intro n hn
    rw [(map_pow ψ (FreeGroup.of 0) n).symm]
    obtain ⟨hdet, hne⟩ := hprop ((FreeGroup.of 0) ^ n) (of_pow_ne_one n hn)
    exact fixed_set_half_sphere_finite _ hdet hne
  exact ⟨ψ (FreeGroup.of 0),
    exists_not_fixed_in_uncountable_sphere (ψ (FreeGroup.of 0)) half_sphere_uncountable hfin⟩

end Problems.Geometry.banach_tarski
