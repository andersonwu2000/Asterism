import Mathlib.Data.ZMod.Basic

namespace Problems.wilson

theorem s124_sub_3 : ∀ p : ℕ, 0 < p → (-1 : ZMod p).val = p - 1 := by
  intro p hp
  cases p with
  | zero => omega
  | succ n => exact ZMod.val_neg_one n

