import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct leaf: conjugation transports the disjoint orbit.
-- (g⁻¹·ρ₀·g)^n = g⁻¹·ρ₀ⁿ·g (conj_pow), so its image of D is g⁻¹ '' (ρ₀ⁿ '' (g '' D));
-- disjointness then transfers across the injective map g⁻¹ via Set.disjoint_image_iff,
-- reducing each pair to the hypothesis h on the ρ₀-orbit of g '' D.
theorem s11456 (g rho0 : E ≃ᵢ E) (D : Set E)
    (h : Pairwise (fun i j : ℕ =>
      Disjoint ((rho0 ^ i) '' (g '' D)) ((rho0 ^ j) '' (g '' D)))) :
    Pairwise (fun i j : ℕ =>
      Disjoint (((g⁻¹ * rho0 * g) ^ i) '' D) (((g⁻¹ * rho0 * g) ^ j) '' D))  := by
  have key : ∀ n : ℕ, ((g⁻¹ * rho0 * g) ^ n) '' D = ⇑g⁻¹ '' ((rho0 ^ n) '' (g '' D)) := by
    intro n
    have hconj : (g⁻¹ * rho0 * g) ^ n = g⁻¹ * rho0 ^ n * g := by
      have : g⁻¹ * rho0 * g = g⁻¹ * rho0 * (g⁻¹)⁻¹ := by rw [inv_inv]
      rw [this, conj_pow, inv_inv]
    rw [hconj]
    simp [Set.image_image, mul_assoc]
  intro i j hij
  rw [key i, key j]
  exact (Set.disjoint_image_iff g⁻¹.injective).mpr (h hij)

end Problems.Geometry.banach_tarski
