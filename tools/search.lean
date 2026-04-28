-- Search tool for Asterism P3 cache subsystem.
--
-- CLI:
--   search --query <text> --scope <mathlib|library> --kind <find_lemmas|find_subgoals|find_pattern|find_mathlib>
--
-- Invocation (Python wrapper Tooling/subsystems/search.py):
--   lake env lean --run tools/search.lean -- \
--       --query "Nat.add_comm" --scope mathlib --kind find_lemmas
--
-- Output (stdout, single line, JSON):
--   {"results": [{"name": "...", "type": "...", "score": <float>}, ...]}
--
-- Exit codes:
--   0 success (empty results array is success — caller checks length)
--   1 CLI argument parse error
--
-- Scope behavior (P3 C20 stub level):
--   mathlib scope: returns []. Full Mathlib declaration walker requires
--                  `import Mathlib` (~22s warm-cache subprocess overhead per
--                  spike-001) and a real namespace search algorithm; deferred
--                  to P5 once construction subsystem demonstrates need.
--   library scope: returns []. Library/Theorems/proved.lean is empty until
--                  P6 promotion code lands (phase3_cache.md §Subsystem says
--                  "P3 stub 回 empty list 並標 caveat").
--
-- The Python wrapper `Tooling/subsystems/search.py` handles `local_goals`
-- scope via direct SQL (no Lean subprocess) and stitches the three scopes.
--
-- Lean core only (no Mathlib import). Subprocess overhead ~2s per spike-009.

import Lean

open Lean

structure SearchResultEntry where
  name  : String
  type  : String
  score : Float := 0.0
deriving ToJson

structure SearchOutput where
  results : Array SearchResultEntry := #[]
deriving ToJson

structure Args where
  query : String
  scope : String     -- "mathlib" | "library"
  kind  : String     -- "find_lemmas" | "find_subgoals" | "find_pattern" | "find_mathlib"

def parseArgs : List String → Option Args
  | rest => parseRest rest none none none
where
  parseRest : List String → Option String → Option String → Option String → Option Args
    | [],                      some q, some s, some k => some { query := q, scope := s, kind := k }
    | [],                      _,      _,      _      => none
    | "--query" :: q :: rest,  _,      s,      k      => parseRest rest (some q) s k
    | "--scope" :: s :: rest,  q,      _,      k      => parseRest rest q (some s) k
    | "--kind"  :: k :: rest,  q,      s,      _      => parseRest rest q s (some k)
    | _ :: rest,               q,      s,      k      => parseRest rest q s k

def main (raw : List String) : IO UInt32 := do
  match parseArgs raw with
  | none =>
      IO.eprintln "usage: search --query <text> --scope <mathlib|library> --kind <find_*>"
      pure 1
  | some args => do
      -- P3 C20 stub: both scopes return empty results. The wire-up exists so
      -- P5/P6 can fill in real implementations without touching the Python
      -- wrapper or search_cache integration.
      let _ := args.query    -- silence unused-variable warnings
      let _ := args.scope
      let _ := args.kind
      let out : SearchOutput := { results := #[] }
      IO.println (toString (toJson out))
      pure 0
