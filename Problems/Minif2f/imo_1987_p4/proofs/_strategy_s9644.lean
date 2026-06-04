import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs.L_residue_fixed_witness

namespace Problems.Minif2f.imo_1987_p4

-- Reduce to finding a residue fixed point in Fin 1987: some a < 1987 with f a ≡ a (mod 1987).
-- Given such a, set n = a and k = f a / 1987; then Nat.div_add_mod gives f a = 1987 * k + a,
-- and a < 1987 with f a % 1987 = a forces f a = a + 1987 * k. The residue witness sub-goal
-- carries the involution-on-odd-set argument (1987 odd ⇒ φ : Fin 1987 → Fin 1987 with φ∘φ=id
-- has a fixed point), while the closer here is mechanical Nat.div_add_mod + omega.
theorem s9644 (f : ℕ → ℕ) (hff : ∀ n, f (f n) = n + 1987) :
    ∃ n, ∃ k, f n = n + 1987 * k  := by
  obtain ⟨a, ha, hfa⟩ := residue_fixed_witness f hff
  refine ⟨a, f a / 1987, ?_⟩
  have hdm : 1987 * (f a / 1987) + f a % 1987 = f a := Nat.div_add_mod (f a) 1987
  omega

end Problems.Minif2f.imo_1987_p4
