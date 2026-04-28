-- Hypothesis carry validator for Asterism P2 Backward pipeline.
--
-- Run via Python (Tooling/stages/validator.py):
--   VALIDATOR_PARENT_TYPE="∀ (n m : Nat), ..."
--   VALIDATOR_SUBGOALS='[{"id":"G001","type_str":"∀ (n : Nat), ..."}]'
--   lake env lean /path/to/tools/validator.lean
--
-- Outputs one JSON line to stdout: Array SubgoalResult
-- (JSON has the same format regardless of Lean diagnostic output on the same stream;
--  Python locates the line starting with "[" to parse it.)
--
-- Lean core only — no Mathlib import.  Startup ~2.5 s (spike-005).
-- impl §4.2: hypothesis_carry CLI behaviour.

import Lean
import Lean.Meta
import Lean.Elab.Command

open Lean Meta Elab Command

-- ================================================================
-- Output types
-- ================================================================

structure TypeMismatch where
  name         : String
  parent_type  : String
  subgoal_type : String
deriving ToJson

structure SubgoalResult where
  subgoal          : String
  missing_binders  : Array String
  type_mismatches  : Array TypeMismatch   -- P3: Meta.isDefEq; P2 always []
deriving ToJson

-- ================================================================
-- Binder extraction
-- ================================================================

/-- Parse *typeStr* as a term, elaborate it, and extract (name, type_string)
    for every ∀-bound variable via forallTelescope.

    Returns #[] on parse or elab error (caller treats as "no binders"). -/
def extractBinders (typeStr : String) : CommandElabM (Array (String × String)) := do
  let env ← getEnv
  match Parser.runParserCategory env `term typeStr "<validator>" with
  | .error _ => return #[]
  | .ok stx  =>
    liftTermElabM do
      try
        let expr ← Term.elabTerm stx none
        let expr ← instantiateMVars expr
        forallTelescope expr fun xs _ => do
          let lctx ← getLCtx
          let mut result : Array (String × String) := #[]
          for x in xs do
            if let some decl := lctx.find? x.fvarId! then
              let tp ← ppExpr decl.type
              result := result.push (decl.userName.toString, s!"{tp}")
          return result
      catch _ => return #[]

-- ================================================================
-- Hypothesis carry check
-- ================================================================

/-- Compare parent binders against sub-goal binders by name.
    Returns a SubgoalResult with missing_binder names filled in.
    type_mismatches is always empty in P2 (P3 adds Meta.isDefEq). -/
def checkCarry
    (subId         : String)
    (parentBinders : Array (String × String))
    (subBinders    : Array (String × String))
    : SubgoalResult :=
  let subNames := subBinders.map (·.1)
  let missing  := parentBinders.filterMap fun (n, _) =>
    if subNames.contains n then none else some n
  { subgoal         := subId
    missing_binders := missing
    type_mismatches := #[] }

-- ================================================================
-- JSON parsing helpers
-- ================================================================

/-- Parse VALIDATOR_SUBGOALS JSON: Array of {id, type_str} objects. -/
def parseSubgoals (s : String) : Array (String × String) :=
  match Json.parse s with
  | .error _  => #[]
  | .ok j =>
    match j.getArr? with
    | .error _   => #[]
    | .ok arr    =>
      arr.filterMap fun item =>
        let id  := (item.getObjVal? "id").toOption.bind       (·.getStr?.toOption)
        let typ := (item.getObjVal? "type_str").toOption.bind (·.getStr?.toOption)
        match id, typ with
        | some i, some t => some (i, t)
        | _,      _      => none

-- ================================================================
-- Entry-point command
-- ================================================================

/-- Main command: reads env vars, runs checks, prints JSON to stdout. -/
syntax "#run_validator" : command

elab_rules : command | `(#run_validator) => do
  let parentType  := (← liftIO (IO.getEnv "VALIDATOR_PARENT_TYPE")).getD  ""
  let subgoalsStr := (← liftIO (IO.getEnv "VALIDATOR_SUBGOALS")).getD     "[]"

  let subgoals    := parseSubgoals subgoalsStr
  let parentBnds  ← extractBinders parentType

  let mut results : Array SubgoalResult := #[]
  for (subId, subTypeStr) in subgoals do
    let subBnds ← extractBinders subTypeStr
    results := results.push (checkCarry subId parentBnds subBnds)

  -- Output JSON; Python finds the line starting with "[".
  liftIO (IO.println (toString (toJson results)))

#run_validator
