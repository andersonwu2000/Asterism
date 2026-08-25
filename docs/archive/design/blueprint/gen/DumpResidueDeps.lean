/-
Blueprint dependency extractor (Residue Theorem).

Dumps the authoritative dependency data straight from the Lean *environment*
(fully-qualified names, kinds, docstrings, and the actual constants each
declaration references). It does NOT read `Library/INDEX.md` (which is
machine-only and may be retired) — the graph is taken from the kernel itself.

Run from the repo root:
    lake env lean blueprint/gen/DumpResidueDeps.lean
Output: blueprint/gen/residue_deps.json
-/
import Library.Analysis.ResidueTheorem.ResidueFormula
import Lean

open Lean

namespace BlueprintGen

/-- Declarations under this namespace are in scope for the blueprint. -/
def targetPrefix : Name := `Library.Analysis.ResidueTheorem

/-- The two defs live under `Complex` but belong to this story. -/
def extraDecls : List Name := [`Complex.windingNumber, `Complex.residue]

def inScope (n : Name) : Bool :=
  (targetPrefix.isPrefixOf n || extraDecls.contains n) && !n.isInternalDetail

def kindStr : ConstantInfo → String
  | .thmInfo _  => "theorem"
  | .defnInfo _ => "def"
  | .axiomInfo _ => "axiom"
  | _ => "other"

def run : CoreM Unit := do
  let env ← getEnv
  -- Pure pass: collect the small set of in-scope (name, info) pairs.
  let inScopeList : List (Name × ConstantInfo) :=
    env.constants.fold (fun acc n ci => if inScope n then (n, ci) :: acc else acc) []
  let scope : Array Name := (inScopeList.map (·.1)).toArray
  let mut objs : Array Json := #[]
  for (n, ci) in inScopeList do
    let doc ← findDocString? env n
    let usedT := ci.type.getUsedConstants
    let usedV := (ci.value?.map (·.getUsedConstants)).getD #[]
    let mut uses : Array Name := #[]
    for c in usedT ++ usedV do
      if c != n && scope.contains c && !uses.contains c then
        uses := uses.push c
    objs := objs.push <| Json.mkObj [
      ("name",   Json.str n.toString),
      ("ns",     Json.str n.getPrefix.toString),
      ("kind",   Json.str (kindStr ci)),
      ("hasDoc", Json.bool doc.isSome),
      ("doc",    Json.str (doc.getD "")),
      ("uses",   Json.arr (uses.map fun c => Json.str c.toString)) ]
  IO.FS.writeFile "blueprint/gen/residue_deps.json" (Json.arr objs).pretty
  IO.println s!"wrote {objs.size} in-scope declarations to blueprint/gen/residue_deps.json"

end BlueprintGen

#eval BlueprintGen.run
