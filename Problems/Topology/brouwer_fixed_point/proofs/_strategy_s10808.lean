import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- Direct proof: pick distinct a b : A (Nontrivial), then f a = f b by Subsingleton,
-- so applying g and assuming g ∘ f = id forces a = b, contradicting hab.
theorem s10808
    {A B : Type*} [Nontrivial A] [Subsingleton B]
    (f : A → B) (g : B → A) :
    g ∘ f ≠ id  := by
  intro h
  obtain ⟨a, b, hab⟩ := exists_pair_ne A
  apply hab
  have hfab : f a = f b := Subsingleton.elim _ _
  have h1 : (g ∘ f) a = a := by rw [h]; rfl
  have h2 : (g ∘ f) b = b := by rw [h]; rfl
  calc a = (g ∘ f) a := h1.symm
    _ = g (f a) := rfl
    _ = g (f b) := by rw [hfab]
    _ = (g ∘ f) b := rfl
    _ = b := h2

end Problems.Topology.brouwer_fixed_point
