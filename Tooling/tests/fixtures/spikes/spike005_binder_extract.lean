-- spike-005: Lean.Elab binder list extraction
-- Goal: verify we can programmatically extract binders (hypotheses) from
-- theorem statements using Lean metaprogramming.
-- This informs the P2 Backward validator's hypothesis carry check design.
--
-- Run from D:/Hadamard:
--   lake env lean D:/Asterism/Tooling/tests/fixtures/spikes/spike005_binder_extract.lean

import Lean
import Lean.Meta
import Lean.Elab.Frontend
import Lean.Elab.Command

open Lean Meta Elab Command

-- ============================================================
-- Part 1: Define sample theorems to inspect
-- ============================================================

-- Sample parent theorem: 3 binders (n, m, h)
theorem sample_parent (n m : Nat) (h : n < m) : n ≤ m :=
  Nat.le_of_lt h

-- Sample sub-goal carrying ALL parent binders (correct hypothesis carry)
theorem sample_subgoal_ok (n m : Nat) (h : n < m) : n + 0 = n :=
  Nat.add_zero n

-- Sample sub-goal missing a binder (incorrect hypothesis carry — missing h)
theorem sample_subgoal_bad (n m : Nat) : n + 0 = n :=
  Nat.add_zero n

-- ============================================================
-- Part 2: #check to verify type signatures
-- ============================================================

#check @sample_parent
-- Expected: ∀ (n m : ℕ), n < m → n ≤ m  (3 binders)

#check @sample_subgoal_ok
-- Expected: ∀ (n m : ℕ), n < m → n + 0 = n  (3 binders — carries all)

#check @sample_subgoal_bad
-- Expected: ∀ (n m : ℕ), n + 0 = n  (2 binders — missing h)

-- ============================================================
-- Part 3: Programmatic binder count via custom elab command
-- ============================================================

syntax "#count_binders" ident : command

elab_rules : command
  | `(#count_binders $id) => do
    let env ← getEnv
    let name := id.getId
    match env.find? name with
    | none => logInfo s!"constant '{name}' not found"
    | some ci =>
      let count ← liftTermElabM (do
        Meta.forallTelescope ci.type fun xs _ => return xs.size)
      logInfo s!"'{name}' has {count} binders"

#count_binders sample_parent
-- Expected: 'sample_parent' has 3 binders

#count_binders sample_subgoal_ok
-- Expected: 'sample_subgoal_ok' has 3 binders

#count_binders sample_subgoal_bad
-- Expected: 'sample_subgoal_bad' has 2 binders

-- ============================================================
-- Part 4: Extract binder names + types
-- Uses getLCtx to access local declarations inside forallTelescope
-- ============================================================

syntax "#show_binders" ident : command

elab_rules : command
  | `(#show_binders $id) => do
    let env ← getEnv
    let name := id.getId
    match env.find? name with
    | none => logInfo s!"constant '{name}' not found"
    | some ci =>
      let info ← liftTermElabM (do
        Meta.forallTelescope ci.type fun xs _ => do
          let lctx ← getLCtx
          let mut pairs : Array String := #[]
          for x in xs do
            match lctx.find? x.fvarId! with
            | none => pairs := pairs.push "(unknown)"
            | some decl =>
              let tp ← Meta.ppExpr decl.type
              pairs := pairs.push s!"({decl.userName} : {tp})"
          return pairs)
      logInfo s!"'{name}' binders: {info}"

#show_binders sample_parent
-- Expected: binders: [(n : ℕ), (m : ℕ), (h : n < m)]

#show_binders sample_subgoal_ok
-- Expected: binders: [(n : ℕ), (m : ℕ), (h : n < m)]

#show_binders sample_subgoal_bad
-- Expected: binders: [(n : ℕ), (m : ℕ)]

-- ============================================================
-- Part 5: Hypothesis carry check (validator logic prototype)
-- Given parent binder count, check if sub-goal has >= that many
-- ============================================================

syntax "#check_hyp_carry" ident "from" ident : command

elab_rules : command
  | `(#check_hyp_carry $sub from $parent) => do
    let env ← getEnv
    let sub_name := sub.getId
    let parent_name := parent.getId
    let sub_ci := env.find? sub_name
    let parent_ci := env.find? parent_name
    match sub_ci, parent_ci with
    | none, _ => logInfo s!"sub-goal '{sub_name}' not found"
    | _, none => logInfo s!"parent '{parent_name}' not found"
    | some sci, some pci =>
      let (sub_count, parent_count) ← liftTermElabM (do
        let sc ← Meta.forallTelescope sci.type fun xs _ => return xs.size
        let pc ← Meta.forallTelescope pci.type fun xs _ => return xs.size
        return (sc, pc))
      let passes := sub_count >= parent_count
      let verdict := if passes then "PASS" else "FAIL"
      logInfo s!"HypCarry({sub_name} from {parent_name}): sub={sub_count} binders, parent={parent_count} binders -> {verdict}"

#check_hyp_carry sample_subgoal_ok from sample_parent
-- Expected: PASS (3 >= 3)

#check_hyp_carry sample_subgoal_bad from sample_parent
-- Expected: FAIL (2 < 3)
