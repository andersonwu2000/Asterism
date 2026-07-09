import Mathlib

set_option linter.style.longLine false

open Finset Function

namespace Problems.Putnam.putnam_2025_a3

noncomputable abbrev putnam_2025_a3_solution : ℕ → Prop := fun _ => False

def GameString (n : ℕ) := Fin n → Fin 3

def initialState (n : ℕ) : GameString n := fun _ => 0

def isValidMove {n : ℕ} (s1 s2 : GameString n) : Prop :=
  (∃! i : Fin n, s1 i ≠ s2 i) ∧
  ∀ i : Fin n, s1 i ≠ s2 i →
    ((s1 i).val + 1 = (s2 i).val ∨ (s2 i).val + 1 = (s1 i).val)

def IsValidGamePlay {n : ℕ} (play : List (GameString n)) : Prop :=
  play.Chain isValidMove (initialState n) ∧
  (initialState n :: play).Nodup

inductive HasWinningStrategy (n : ℕ) : List (GameString n) → Prop where
  | win (play : List (GameString n)) (s : GameString n) :
      IsValidGamePlay (play ++ [s]) →
      (∀ s', IsValidGamePlay (play ++ [s, s']) → HasWinningStrategy n (play ++ [s, s'])) →
      HasWinningStrategy n play

def AliceHasWinningStrategy (n : ℕ) : Prop := HasWinningStrategy n []

end Problems.Putnam.putnam_2025_a3
