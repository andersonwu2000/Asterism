import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_winding_int_iso_data

namespace Problems.pi1_circle

-- Strip the `Multiplicative ℤ` wrapping to an additive winding function
-- `W : FundamentalGroup Circle 1 → ℤ` with the three monoid-relevant properties
-- (W 1 = 0, W (a*b) = W a + W b, bijective); the combinator packages those into a
-- bijective MonoidHom via `Multiplicative.ofAdd ∘ W`. Sub-goal isolates the winding
-- construction (Forward bricks + monodromy_*); combinator is pure plumbing.
theorem s10689 :
    ∃ (φ : FundamentalGroup Circle 1 →* Multiplicative ℤ), Function.Bijective φ  := by
  have h_winding := winding_int_iso_data
  obtain ⟨W, h_one, h_mul, h_bij⟩ := h_winding
  refine ⟨{
    toFun := fun a => Multiplicative.ofAdd (W a)
    map_one' := by
      change Multiplicative.ofAdd (W 1) = 1
      rw [h_one]
      rfl
    map_mul' := fun a b => by
      change Multiplicative.ofAdd (W (a * b))
        = Multiplicative.ofAdd (W a) * Multiplicative.ofAdd (W b)
      rw [h_mul]
      rfl
  }, ?_⟩
  refine ⟨?inj, ?surj⟩
  · intro a b h
    apply h_bij.1
    exact Multiplicative.ofAdd.injective h
  · intro y
    obtain ⟨a, ha⟩ := h_bij.2 y.toAdd
    refine ⟨a, ?_⟩
    change Multiplicative.ofAdd (W a) = y
    rw [ha]
    rfl

end Problems.pi1_circle
