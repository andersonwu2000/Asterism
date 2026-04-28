-- Dedupe tool for Asterism P3 cache subsystem.
--
-- CLI (impl §7.1):
--   dedupe --candidate <stmt_file> --against <list_file> --mode <strict|iff_lite>
--
-- Invocation (Python wrapper Tooling/subsystems/dedupe.py):
--   lake env lean --run tools/dedupe.lean -- \
--       --candidate <candidate.lean> --against <entries.json> --mode strict
--
-- Input formats:
--   <candidate.lean>: a single-theorem file with `theorem _candidate : <type> := sorry`
--                     (or any user-declared theorem; first one wins, same as validator.lean).
--   <entries.json>:   JSON array of entries:
--                     [{"id": 1, "lean_path": "/abs/path/to/entry1.lean"}, ...]
--
-- Output (stdout, single line, JSON):
--   {"result": "hit", "entry_id": <int>}        -- first matching entry's id
--   {"result": "novel"}                         -- no entry matched OR
--                                                  candidate failed to elaborate
--                                                  (spec §7.1: "elaborate 失敗
--                                                  → NOVEL, 容錯不報錯")
--
-- Exit codes:
--   0 success.
--   1 CLI argument parse error.
--
-- Diagnostics: when candidate (or entries.json) fails to load/elaborate,
-- a `warn: ...` line is written to stderr for debugging; stdout still gets
-- the spec-compliant `{"result": "novel"}` so callers don't have to handle
-- a third outcome kind.
--
-- Mode behavior (impl §7.1):
--   strict:    elaborate candidate; on success, for each entry elaborate +
--              isDefEq compare candidate.type vs entry.type; first hit wins.
--   iff_lite:  strict + on miss try `theorem _check : <c> ↔ <e> := by
--              simp; try decide; try norm_num; ring_nf` per pair with 5s
--              timeout (P3 C20: stub returns same as strict; full iff_lite
--              wired in C23 once Backward integrates dedupe.lean and spike-009
--              measures real isDefEq cost).
--
-- Lean core only (no Mathlib import on this file). Matches validator.lean
-- design — keeps subprocess overhead ~2s per spike-009 D-09-1.

import Lean
import Lean.Elab.Frontend
import Lean.Meta.Basic
import Lean.Meta.ExprDefEq

open Lean Lean.Meta Lean.Elab

-- ================================================================
-- Output JSON
-- ================================================================

structure DedupeOutput where
  result   : String         -- "hit" | "novel"
  entry_id : Option Int := none
deriving ToJson

-- ================================================================
-- File elaboration via Lean.Elab.runFrontend (re-uses validator.lean pattern)
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

/-- Elaborate `path` and return (env, theorem-type-Expr).
    Errors propagate as `Except String`. -/
def fileTheoremType (path : String) : IO (Except String (Environment × Expr)) := do
  try
    let content ← IO.FS.readFile path
    let (env, ok) ← Lean.Elab.runFrontend content {} path `_AsterismDedupe
    if !ok then
      return .error s!"runFrontend reported errors in {path}"
    match findUserTheorem env with
    | none => return .error s!"no user theorem found in {path}"
    | some thmName =>
      match env.find? thmName with
      | none    => return .error s!"theorem {thmName} not in env after runFrontend"
      | some ci => return .ok (env, ci.type)
  catch e =>
    return .error s!"IO error on {path}: {e.toString}"

-- ================================================================
-- isDefEq compare
-- ================================================================

/-- Run `Lean.Meta.isDefEq candType entryType` in MetaM with the candidate's env.

    Cross-env caveat: if entryType references constants only in entryEnv (not
    in candEnv), isDefEq will report false. For P3 demo theorems (Lean core
    types: Nat / List / Eq), this is acceptable; real Mathlib-aware dedupe is
    C23 work + spike-009 follow-up if isDefEq retry storm becomes real. -/
def runIsDefEq (candEnv : Environment) (candType entryType : Expr) : IO Bool := do
  let coreCtx : Core.Context := { fileName := "_dedupe", fileMap := default }
  let coreState : Core.State := { env := candEnv }
  try
    let metaResult ← (Meta.isDefEq candType entryType).run'.toIO coreCtx coreState
    return metaResult
  catch _ =>
    -- isDefEq crashed (likely missing constants in env); treat as no match
    return false

-- ================================================================
-- Entries JSON parse
-- ================================================================

structure Entry where
  id        : Int
  lean_path : String
deriving FromJson

def parseEntries (jsonText : String) : Except String (Array Entry) := do
  let json ← Json.parse jsonText
  fromJson? json

-- ================================================================
-- CLI argument parsing
-- ================================================================

structure Args where
  candidate : String
  against   : String
  mode      : String     -- "strict" | "iff_lite"

def parseArgs : List String → Option Args
  | rest => parseRest rest none none "strict"
where
  parseRest : List String → Option String → Option String → String → Option Args
    | [],                       some c, some a, m => some { candidate := c, against := a, mode := m }
    | [],                       _,      _,      _ => none
    | "--candidate" :: c :: rest, _,    a,      m => parseRest rest (some c) a m
    | "--against"   :: a :: rest, c,    _,      m => parseRest rest c (some a) m
    | "--mode"      :: m :: rest, c,    a,      _ => parseRest rest c a m
    | _ :: rest,                  c,    a,      m => parseRest rest c a m

-- ================================================================
-- Main
-- ================================================================

def main (raw : List String) : IO UInt32 := do
  match parseArgs raw with
  | none =>
      IO.eprintln "usage: dedupe --candidate <file> --against <entries.json> --mode <strict|iff_lite>"
      pure 1
  | some args => do
      -- Elaborate candidate
      let candRes ← fileTheoremType args.candidate
      match candRes with
      | .error err =>
          -- spec §7.1: "elaborate 失敗 → NOVEL, 容錯不報錯"
          IO.eprintln s!"warn: candidate elab failed: {err}"
          let out : DedupeOutput := { result := "novel" }
          IO.println (toString (toJson out))
          pure 0
      | .ok (candEnv, candType) =>
          -- Parse entries JSON
          let entriesText ← (try IO.FS.readFile args.against
                              catch _ => pure "[]")
          match parseEntries entriesText with
          | .error err =>
              -- entries malformed → no entries to compare → NOVEL
              IO.eprintln s!"warn: entries.json parse: {err}"
              let out : DedupeOutput := { result := "novel" }
              IO.println (toString (toJson out))
              pure 0
          | .ok entries =>
              -- Loop entries; first hit wins
              let mut hitId : Option Int := none
              for entry in entries do
                let entryRes ← fileTheoremType entry.lean_path
                match entryRes with
                | .error _ => continue  -- entry elab failed; skip
                | .ok (_, entryType) =>
                    let same ← runIsDefEq candEnv candType entryType
                    if same then
                      hitId := some entry.id
                      break
              match hitId with
              | some id =>
                  let out : DedupeOutput := { result := "hit", entry_id := some id }
                  IO.println (toString (toJson out))
              | none =>
                  -- iff_lite mode: P3 C20 stub returns same as strict.
                  -- TODO C23: wire `theorem _check : c ↔ e := by simp; ...`
                  -- per impl §7.1 once Backward integration measures real cost.
                  let _ := args.mode  -- silence unused-variable warning until C23
                  let out : DedupeOutput := { result := "novel" }
                  IO.println (toString (toJson out))
              pure 0
