import Mathlib

namespace Problems.cantor

theorem main : ∀ f : ℕ → Set ℕ, ∃ S : Set ℕ, ∀ n : ℕ, f n ≠ S := by
  intro f
  use {n | n ∉ f n}
  intro n h
  have key : n ∈ f n ↔ n ∉ f n := by
    constructor
    · intro hm; rw [h] at hm; exact hm
    · intro hm; rw [h]; exact hm
  exact iff_not_self key

end Problems.cantor
