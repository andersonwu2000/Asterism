import Mathlib

set_option linter.style.longLine false

open Finset

namespace Problems.PutnamCmp.putnam_2025_a5

noncomputable abbrev putnam_2025_a5_solution : (n : ℕ) → Set (Fin n → ℤˣ) := fun n => {s | (∀ i : Fin n, s i = (-1) ^ (i.val + 1)) ∨ (∀ i : Fin n, s i = (-1) ^ i.val)}

def f (n : ℕ) (s : Fin n → ℤˣ) : ℕ :=
  Finset.card {σ : Equiv.Perm (Fin (n + 1)) |
    ∀ i : Fin n, 0 < (s i : ℤ) * ((σ i.succ : ℤ) - (σ i.castSucc : ℤ))}

end Problems.PutnamCmp.putnam_2025_a5
