-- Hypothesis carry validator for Asterism P2 Backward pipeline.
--
-- CLI (impl §4.2):
--   validator hypothesis_carry --parent <file> --subgoals <file>...
--
-- Invocation (Python wrapper Tooling/stages/validator.py):
--   lake env lean --run tools/validator.lean -- hypothesis_carry \
--       --parent <parent.lean> --subgoals <sub1.lean> <sub2.lean> ...
--
-- Output (stdout, single line, JSON):
--   {"parent_error": null|"<msg>",
--    "subgoals": [
--      {"subgoal": "<path>", "missing_binders": ["<n>"...], "error": null|"<msg>"}
--    ]}
--
-- Exit codes:
--   0 success
--   1 CLI argument parse error
--   2 parent file failed to elaborate (subgoals not checked)
--
-- Behavior (impl §4.2 / spike-005):
--   - For each .lean file, run Lean.Elab.runFrontend on its content.
--   - Locate the first user-declared theorem (env.getModuleIdxFor? = none).
--   - Walk the theorem's type Expr to collect ∀-binder names — no MetaM,
--     no ppExpr (audit C11.R2 #6: type strings are dead work for P2/P3).
--   - Compare parent binder names against subgoal binder names.
--
-- Lean core only (no Mathlib import on this file itself; subgoal files'
-- imports are loaded by runFrontend as needed).

import Lean
import Lean.Elab.Frontend

open Lean

-- ================================================================
-- Output types
-- ================================================================

structure SubgoalResult where
  subgoal         : String
  missing_binders : Array String
  error           : Option String := none
deriving ToJson

structure ValidatorOutput where
  parent_error : Option String  := none
  subgoals     : Array SubgoalResult := #[]
deriving ToJson

-- ================================================================
-- Binder extraction (pure Expr walk, no MetaM)
-- ================================================================

/-- Collect ∀-binder names by walking the Expr tree. -/
partial def collectForallBinders : Expr → Array Name
  | .forallE n _ body _ => #[n] ++ collectForallBinders body
  | _                   => #[]

-- ================================================================
-- File elaboration via Lean.Elab.runFrontend
-- ================================================================

/-- True iff `name` was declared in the current file (not from imports). -/
def isUserDecl (env : Environment) (name : Name) : Bool :=
  env.getModuleIdxFor? name |>.isNone

/-- Find the first user-declared theorem in `env`. -/
def findUserTheorem (env : Environment) : Option Name :=
  env.constants.toList.findSome? fun (name, info) =>
    match info with
    | .thmInfo _ => if isUserDecl env name then some name else none
    | _          => none

/-- Elaborate file at `path` and return its theorem's binder names.
    Errors propagate as `Except String`.
    P6.x patch 9 (Lean v4.30 toolchain drift): runFrontend returns
    `IO (Option Environment)` — `none` means errors. -/
def fileBinders (path : String) : IO (Except String (Array Name)) := do
  try
    let content ← IO.FS.readFile path
    let env? ← Lean.Elab.runFrontend content {} path `_AsterismValidator
    match env? with
    | none => return .error s!"runFrontend reported errors in {path}"
    | some env =>
      match findUserTheorem env with
      | none => return .error s!"no user theorem found in {path}"
      | some thmName =>
        match env.find? thmName with
        | none    => return .error s!"theorem {thmName} not in env after runFrontend"
        | some ci => return .ok (collectForallBinders ci.type)
  catch e =>
    return .error s!"IO error on {path}: {e.toString}"

-- ================================================================
-- CLI argument parsing
-- ================================================================

structure Args where
  parent   : String
  subgoals : Array String

/-- Parse args:  hypothesis_carry --parent <file> --subgoals <file>... -/
def parseArgs : List String → Option Args
  | "hypothesis_carry" :: rest => parseRest rest none #[]
  | _                          => none
where
  parseRest : List String → Option String → Array String → Option Args
    | [],                              some p, sgs => some { parent := p, subgoals := sgs }
    | [],                              none,   _   => none
    | "--parent"   :: p :: rest, _,     sgs        => parseRest rest (some p) sgs
    | "--subgoals" :: rest,      some p, sgs       =>
        some { parent := p, subgoals := sgs ++ rest.toArray }
    | "--subgoals" :: _,         none,   _         => none
    | _ :: rest,                 parent, sgs       => parseRest rest parent sgs

-- ================================================================
-- Main
-- ================================================================

def main (raw : List String) : IO UInt32 := do
  match parseArgs raw with
  | none =>
      IO.eprintln
        "usage: validator hypothesis_carry --parent <file> --subgoals <file>..."
      pure 1
  | some args =>
      let parentRes ← fileBinders args.parent
      match parentRes with
      | .error err =>
          let out : ValidatorOutput := { parent_error := some err }
          IO.println (toString (toJson out))
          pure 2
      | .ok parentBnds =>
          let mut results : Array SubgoalResult := #[]
          for sub in args.subgoals do
            let r ← fileBinders sub
            match r with
            | .error err =>
                results := results.push
                  { subgoal := sub, missing_binders := #[], error := some err }
            | .ok subBnds =>
                let missing := parentBnds.filter (fun n => !subBnds.contains n)
                results := results.push
                  { subgoal := sub, missing_binders := missing.map (·.toString) }
          let out : ValidatorOutput := { subgoals := results }
          IO.println (toString (toJson out))
          pure 0
