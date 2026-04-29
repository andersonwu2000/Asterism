import Mathlib

namespace Problems.cantor

theorem main : ∀ f : ℕ → Set ℕ, ∃ S : Set ℕ, ∀ n : ℕ, f n ≠ S := by decide

end Problems.cantor
