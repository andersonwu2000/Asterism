-- Hypothesis carry validator for Asterism Backward pipeline.
--
-- Two CLI modes:
--   1. hypothesis_carry (legacy, per-file): one runFrontend per .lean file;
--      Mathlib import re-loaded N+1 times (parent + N subgoals). 60-120s
--      per call → 600s+ for typical Path B → unusable in real runs.
--   2. hypothesis_carry_batch (P6.x patch 29): synthesize ONE combined
--      .lean source containing parent + all subgoals as separate theorems,
--      one runFrontend call, walk env once. Mathlib loads once, total
--      time ~= one cold load.
--
-- Batch CLI (impl §4.2 patch 29):
--   validator hypothesis_carry_batch --json <input.json>
--
--   input.json shape:
--     {"problem": "<p>",
--      "parent":   {"slug": "<slug>", "statement": "<lean type expr>"},
--      "subgoals": [{"slug": "<slug>", "statement": "<lean type expr>"}, ...],
--      "imports":  ["Problems.<p>.Defs", ...]}
--
-- Legacy CLI:
--   validator hypothesis_carry --parent <file> --subgoals <file>...
--
-- Output (stdout, single line, JSON):
--   {"parent_error": null|"<msg>",
--    "subgoals": [
--      {"subgoal": "<slug-or-path>", "missing_binders": ["<n>"...],
--       "error": null|"<msg>"}
--    ]}
--
-- Exit codes:
--   0 success
--   1 CLI argument parse error
--   2 parent failed to elaborate (subgoals not checked)
--
-- Behavior (impl §4.2 / spike-005):
--   - For each input theorem, run Lean.Elab.runFrontend.
--   - Locate the user-declared theorem(s) by name pattern.
--   - Walk the theorem's type Expr to collect ∀-binder names — no MetaM,
--     no ppExpr (audit C11.R2 #6: type strings are dead work for P2/P3).
--   - Compare parent binder names against subgoal binder names.
--
-- Lean core + Lean.Data.Json only on this file itself; user theorems'
-- imports (Problems.<p>.Defs, transitively Mathlib) loaded by runFrontend.

import Lean
import Lean.Elab.Frontend
import Lean.Data.Json

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
unsafe def fileBinders (path : String) : IO (Except String (Array Name)) := do
  try
    let content ← IO.FS.readFile path
    -- v4.30: must be called before EACH runFrontend, not just once.
    Lean.enableInitializersExecution
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
-- Batch mode (P6.x patch 29): single-runFrontend over synthesized
-- combined source — Mathlib loads once amortizing cost across N subgoals.
-- ================================================================

structure SubgoalSpec where
  slug      : String
  statement : String
deriving FromJson

structure ParentSpec where
  slug      : String
  statement : String
deriving FromJson

structure BatchInput where
  problem  : String
  parent   : ParentSpec
  subgoals : Array SubgoalSpec
  imports  : Array String := #[]
deriving FromJson

/-- Build the synthesized .lean source string for one runFrontend call.

    Header is `import` lines from `imports` (defaults to `Problems.<p>.Defs`
    when caller omits). Each theorem is declared with a sentinel name so we
    can locate it by name rather than ordering after elaboration:
      `theorem _val_parent_<parent_slug> : <stmt> := sorry`
      `theorem _val_sg_<sg_slug>          : <stmt> := sorry`
    Sentinel collisions are caller's responsibility (slugs are unique within
    one Backward proposal). -/
def synthesizeBatchSource (inp : BatchInput) : String :=
  let importsList :=
    if inp.imports.isEmpty then #[s!"Problems.{inp.problem}.Defs"]
    else inp.imports
  let importLines := importsList.foldl (fun acc i => acc ++ s!"import {i}\n") ""
  let parentDecl :=
    s!"theorem _val_parent_{inp.parent.slug} : {inp.parent.statement} := sorry\n"
  let sgDecls := inp.subgoals.foldl
    (fun acc sg =>
       acc ++ s!"theorem _val_sg_{sg.slug} : {sg.statement} := sorry\n")
    ""
  importLines ++ "\n" ++ parentDecl ++ sgDecls

/-- Run batch validation. Returns the structured ValidatorOutput; the caller
    serializes to JSON.

    Failure model:
      - JSON parse failure: caller produces `parent_error` saying so.
      - runFrontend env? = none: synthesized source had elab errors. We
        cannot attribute per-theorem (Lean prints diagnostics to stderr,
        not env). Surface as `parent_error` so the wrapper logs the run
        failure rather than silently passing all subgoals. -/
unsafe def runBatch (inp : BatchInput) : IO ValidatorOutput := do
  let src := synthesizeBatchSource inp
  Lean.enableInitializersExecution
  let env? ← Lean.Elab.runFrontend src {} "<asterism_validator_batch>"
                 `_AsterismValidatorBatch
  match env? with
  | none =>
    let out : ValidatorOutput :=
      { parent_error :=
          some "runFrontend reported errors elaborating synthesized batch source" }
    return out
  | some env =>
    let parentName := Name.mkSimple s!"_val_parent_{inp.parent.slug}"
    match env.find? parentName with
    | none =>
      let out : ValidatorOutput :=
        { parent_error :=
            some s!"parent theorem {parentName} not in env after batch runFrontend" }
      return out
    | some pci =>
      let parentBnds := collectForallBinders pci.type
      let mut results : Array SubgoalResult := #[]
      for sg in inp.subgoals do
        let nm := Name.mkSimple s!"_val_sg_{sg.slug}"
        match env.find? nm with
        | none =>
          results := results.push
            { subgoal := sg.slug, missing_binders := #[],
              error := some s!"subgoal {sg.slug} not found in synthesized env" }
        | some ci =>
          let bnds := collectForallBinders ci.type
          let missing := parentBnds.filter (fun n => !bnds.contains n)
          results := results.push
            { subgoal := sg.slug, missing_binders := missing.map (·.toString) }
      let out : ValidatorOutput := { subgoals := results }
      return out

-- ================================================================
-- CLI argument parsing
-- ================================================================

inductive ParsedArgs
  | legacy   (parent : String) (subgoals : Array String)
  | batch    (jsonPath : String)

/-- Parse args. Two modes:
      hypothesis_carry --parent <file> --subgoals <file>...
      hypothesis_carry_batch --json <input.json>
-/
def parseArgs : List String → Option ParsedArgs
  | "hypothesis_carry"       :: rest => parseLegacy rest none #[]
  | "hypothesis_carry_batch" :: rest => parseBatch rest
  | _                                => none
where
  parseLegacy : List String → Option String → Array String → Option ParsedArgs
    | [],                              some p, sgs => some (.legacy p sgs)
    | [],                              none,   _   => none
    | "--parent"   :: p :: rest, _,     sgs        => parseLegacy rest (some p) sgs
    | "--subgoals" :: rest,      some p, sgs       =>
        some (.legacy p (sgs ++ rest.toArray))
    | "--subgoals" :: _,         none,   _         => none
    | _ :: rest,                 parent, sgs       => parseLegacy rest parent sgs
  parseBatch : List String → Option ParsedArgs
    | "--json" :: p :: _ => some (.batch p)
    | _                  => none

-- ================================================================
-- Main
-- ================================================================

unsafe def main (raw : List String) : IO UInt32 := do
  -- P6.x patch (Lean v4.30): runFrontend requires
  -- enableInitializersExecution before importModules.
  Lean.enableInitializersExecution
  match parseArgs raw with
  | none =>
      IO.eprintln
        ("usage:\n  validator hypothesis_carry "
         ++ "--parent <file> --subgoals <file>...\n"
         ++ "  validator hypothesis_carry_batch --json <input.json>")
      pure 1
  | some (.legacy parent subgoals) =>
      let parentRes ← fileBinders parent
      match parentRes with
      | .error err =>
          let out : ValidatorOutput := { parent_error := some err }
          IO.println (toJson out).compress
          pure 2
      | .ok parentBnds =>
          let mut results : Array SubgoalResult := #[]
          for sub in subgoals do
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
          IO.println (toJson out).compress
          pure 0
  | some (.batch jsonPath) =>
      try
        let raw ← IO.FS.readFile jsonPath
        match Json.parse raw with
        | .error msg =>
            let out : ValidatorOutput :=
              { parent_error := some s!"JSON parse error in {jsonPath}: {msg}" }
            IO.println (toJson out).compress
            pure 2
        | .ok j =>
          match (FromJson.fromJson? j : Except String BatchInput) with
          | .error msg =>
              let out : ValidatorOutput :=
                { parent_error :=
                    some s!"JSON shape error in {jsonPath}: {msg}" }
              IO.println (toJson out).compress
              pure 2
          | .ok inp =>
              let out ← runBatch inp
              IO.println (toJson out).compress
              match out.parent_error with
              | none => pure 0
              | some _ => pure 2
      catch e =>
        let out : ValidatorOutput :=
          { parent_error := some s!"IO error reading {jsonPath}: {e.toString}" }
        IO.println (toJson out).compress
        pure 2
