import Lean.Server.Rpc.RequestHandling
import Lean.Server.FileWorker
import Lean.Server.Watchdog
import Lean.Util.CollectAxioms
import Lean.Environment

/-!
# Asterism gateway custom RPC handlers

Registers two builtin RPC procedures on the Lean LSP worker:

  * `Asterism.writeOlean` — serialize the worker's current `Environment`
    to a `.olean` file at a given destination. Used by the framework
    after a successful `verify` to make the just-elaborated module
    available to subsequent cascade layers (which import it by module
    name) without a separate `lake build` round-trip.

  * `Asterism.printAxioms` — return the transitive axiom set for a
    given fully-qualified name. Replaces a `lake env lean … #print
    axioms` subprocess (~5-15s) with an in-worker call (~50-200ms).

Built into a custom `lean-asterism-server` binary that the gateway
spawns instead of stock `lean --server`. Works because the worker
process loads this module's `builtin_initialize` block at startup,
which registers the procedures into `builtinRpcProcedures` (global,
NOT env-scoped) — visible to every RPC client regardless of which
file the slot has open.

The binary's `main` dispatches on `argv` to either watchdog or
worker mode, mirroring stock `lean --server` / `lean --worker`.
-/

open Lean Server

namespace Asterism

/-! ## Snapshot tree walker

`doc.cmdSnaps` is the "old representation for backward compatibility"
and is built via a `private_decl%` default field initializer that
captures `initSnap` at construction time — when the parser hasn't
yet completed, `mkCmdSnaps` returns `.nil` and locks that in. We
therefore can't rely on `cmdSnaps.waitAll` to give us a populated
list. Instead, traverse `doc.initSnap` directly:

  initSnap (HeaderParsedSnapshot)
    .result? → headerParsed
      .processedSnap → HeaderProcessedSnapshot
        .result? → headerSuccess
          .firstCmdSnap → CommandParsedSnapshot (chained via `nextCmdSnap?`)
            .elabSnap.resultSnap → CommandResultSnapshot
              .cmdState.env  ← this is what we want, post all elab.
-/

/-- Result of the snapshot tree walk. `env` is `some` only when the
walker reached a terminal command's elaboration result. `trace` is
a short diagnostic string for the failure case. -/
structure WalkResult where
  env : Option Environment := none
  trace : String

instance : Inhabited WalkResult := ⟨{ trace := "" }⟩

open Language.Lean in
/-- Walk to the LAST command's elaboration result and return its
post-elaborate environment + a trace string indicating where the
walk terminated. -/
partial def lastCmdEnv (doc : Server.FileWorker.EditableDocument) :
    ServerTask WalkResult := Id.run do
  let some headerParsed := doc.initSnap.result?
    | .pure { trace := "initSnap.result? is none (header parse failed)" }
  headerParsed.processedSnap.task.asServerTask.bindCheap fun headerProcessed =>
    Id.run do
      let some headerSuccess := headerProcessed.result?
        | .pure { trace := "headerProcessed.result? is none (import failed)" }
      headerSuccess.firstCmdSnap.task.asServerTask.bindCheap (walk 0)
where
  walk (depth : Nat) (cmd : CommandParsedSnapshot) : ServerTask WalkResult := Id.run do
    match cmd.nextCmdSnap? with
    | none =>
        cmd.elabSnap.resultSnap.task.asServerTask.bindCheap fun result =>
          .pure { env := some result.cmdState.env, trace := s!"ok (cmd depth {depth})" }
    | some next =>
        next.task.asServerTask.bindCheap (walk (depth + 1))

/-! ## writeOlean -/

structure WriteOleanParams where
  destPath : String
  deriving FromJson, ToJson

instance : RpcEncodable WriteOleanParams := inferInstance

structure WriteOleanResp where
  ok : Bool
  error : Option String := none
  deriving FromJson, ToJson

instance : RpcEncodable WriteOleanResp := inferInstance

/-- Wait for the file's terminal snapshot (whole file elaborated),
then call `Lean.writeModule` on the resulting env. IO errors are
captured into `error` rather than surfaced as RPC failures so the
client gets a structured response. -/
def writeOleanImpl (p : WriteOleanParams) : RequestM (RequestTask WriteOleanResp) := do
  let doc ← RequestM.readDoc
  RequestM.mapTaskCostly (lastCmdEnv doc) fun walkResult => do
    match walkResult.env with
    | none => return { ok := false, error := some s!"no terminal snapshot: {walkResult.trace}" }
    | some env =>
        let r ← (Lean.writeModule env
                  (System.FilePath.mk p.destPath) (writeIR := false)).toBaseIO
        match r with
        | .ok _ => return { ok := true }
        | .error e => return { ok := false, error := some (toString e) }

/-! ## printAxioms -/

structure PrintAxiomsParams where
  fqName : String
  deriving FromJson, ToJson

instance : RpcEncodable PrintAxiomsParams := inferInstance

structure PrintAxiomsResp where
  found : Bool
  axioms : Array String
  error : Option String := none
  deriving FromJson, ToJson

instance : RpcEncodable PrintAxiomsResp := inferInstance

/-- Parse dotted name string `Foo.Bar.baz` into `Lean.Name`. -/
private def parseQualifiedName (s : String) : Name :=
  s.splitOn "." |>.foldl (fun acc seg => Name.mkStr acc seg) Name.anonymous

/-- Resolve `fqName` in the worker's env, then walk its kernel
dependency graph collecting axioms. Mirrors what `#print axioms`
does internally but returns a structured list.

Runs `Lean.collectAxioms` inside `CoreM.toIO'` with a minimal
context so we can call from a server-RPC context (no Lean elab
state available). -/
def printAxiomsImpl (p : PrintAxiomsParams) : RequestM (RequestTask PrintAxiomsResp) := do
  let doc ← RequestM.readDoc
  RequestM.mapTaskCostly (lastCmdEnv doc) fun walkResult => do
    match walkResult.env with
    | none =>
        return { found := false, axioms := #[],
                 error := some s!"no terminal snapshot: {walkResult.trace}" }
    | some env =>
        let n := parseQualifiedName p.fqName
        if env.find? n |>.isNone then
          return {
            found := false, axioms := #[],
            error := some s!"constant not found: {p.fqName}"
          }
        let coreCtx : Core.Context := { fileName := "", fileMap := default }
        let coreState : Core.State := { env }
        let r ← (Lean.collectAxioms (m := CoreM) n).toIO' coreCtx coreState |>.toBaseIO
        match r with
        | .ok axs =>
            return { found := true, axioms := axs.map (·.toString) }
        | .error e =>
            return { found := false, axioms := #[], error := some (toString e) }

/-! ## anchorClosure

Given a fully-qualified name, walk its **definitional dependency
closure** and return the constants that are NOT in the trust base
(Mathlib ∪ Library ∪ core). These are the "pending anchors" — defs the
framework itself generated that the top statement's meaning rests on,
which a human must vouch for.

This is the anchor+claim architecture's TCB (`anchor_claim_design.md`
§4). Correctness = zero-leak: every non-trusted constant reachable
through the statement's type (and, recursively, through the type + body
of each non-trusted def it uses) MUST appear. It is a KERNEL walk over
`Expr.getUsedConstants` + `Environment.getModuleIdxFor?` module
provenance — NEVER a text/regex scan of source (a regex reading a
docstring token as a decl name here would silently hand a human an
incomplete set to sign → a false theorem).

Asymmetry vs the top node's PROOF: we walk only the top node's TYPE
(the statement), never its proof term. The proof's trust is the kernel
+ the axiom whitelist (`printAxioms`); the statement's trust is this
closure. The two probes are complementary.

Classification rule (fail-closed): a constant is trusted iff its
declaring module's root component is one of `trustedRoots`. `none`
module (a local same-file decl) and every `Problems.*` / unknown
module → pending. Over-surfacing is safe; under-surfacing is not. -/

structure AnchorEntry where
  name : String
  module : String
  kind : String
  deriving FromJson, ToJson

instance : RpcEncodable AnchorEntry := inferInstance

structure AnchorClosureParams where
  fqName : String
  deriving FromJson, ToJson

instance : RpcEncodable AnchorClosureParams := inferInstance

structure AnchorClosureResp where
  found : Bool
  topKind : String := ""
  topIsProp : Bool := false
  topModule : String := ""
  pending : Array AnchorEntry := #[]
  error : Option String := none
  deriving FromJson, ToJson

instance : RpcEncodable AnchorClosureResp := inferInstance

/-- Module roots we trust by assumption (the TCB boundary). `Library`
= the framework's harvested shared library; the rest are Lean/Mathlib
core. Anything else is a pending anchor. -/
private def trustedRoots : List Name := [`Mathlib, `Library, `Init, `Std, `Lean]

/-- Module a constant was declared in, or `none` if it is local to the
current (probed) file. `getModuleIdxFor?` returns `none` precisely for
non-imported decls. -/
private def moduleNameFor (env : Environment) (n : Name) : Option Name :=
  match env.getModuleIdxFor? n with
  | some idx => env.allImportedModuleNames[idx.toNat]?
  | none     => none

/-- Fail-closed trust test: trusted iff the declaring module's root
component is in `trustedRoots`. Local (`none` module) → not trusted. -/
private def isTrusted (env : Environment) (n : Name) : Bool :=
  match moduleNameFor env n with
  | some mod => trustedRoots.contains mod.getRoot
  | none     => false

private def kindStr : ConstantInfo → String
  | .axiomInfo _  => "axiom"
  | .defnInfo _   => "def"
  | .thmInfo _    => "thm"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _   => "quot"
  | .inductInfo _ => "induct"
  | .ctorInfo _   => "ctor"
  | .recInfo _    => "rec"

/-- Constants a decl's MEANING depends on. For a genuine data
definition we include its body (the construction IS part of the
meaning); for a theorem / opaque, or for a `def` whose type is a
`Prop` (a proof-carrying claim wrapper such as the framework's
`def main := proof`), we take the TYPE only — the proof is irrelevant
to what the statement means. Predicates (`def P : α → Prop := …`) are
data: their type is `α → Prop`, not itself a `Prop`, so `isProp` is
false and their body IS walked. Inductives contribute their ctors.
Runs in `MetaM` for the `isProp` decision. -/
private def constDepsM (info : ConstantInfo) : Meta.MetaM (Array Name) := do
  let tyDeps := info.type.getUsedConstants
  let bodyDeps : Array Name ← match info with
    | .defnInfo v =>
        if ← Meta.isProp info.type then pure #[] else pure v.value.getUsedConstants
    | _ => pure #[]   -- thm / opaque / quot / inductive / ctor / rec: type only
  let extra := match info with
    | .inductInfo v => v.ctors.toArray
    | _             => #[]
  return tyDeps ++ bodyDeps ++ extra

/-- Worklist walk in `MetaM` (needed for the body-vs-proof `isProp`
decision). `visited` prevents revisiting / cycles; trusted constants
terminate a branch; non-trusted ones are recorded and recursed through
`constDepsM`. -/
private partial def anchorWalkM (visited : NameSet) (acc : Array AnchorEntry) :
    List Name → Meta.MetaM (Array AnchorEntry)
  | []        => return acc
  | n :: rest => do
      if visited.contains n then
        anchorWalkM visited acc rest
      else
        let visited := visited.insert n
        let env ← getEnv
        if isTrusted env n then
          anchorWalkM visited acc rest
        else
          match env.find? n with
          | none =>
              -- Not in env: fail-closed, surface as an unknown pending.
              anchorWalkM visited
                (acc.push { name := n.toString, module := "", kind := "unknown" }) rest
          | some info =>
              let deps ← constDepsM info
              -- Skip compiler-generated auxiliaries (`_proof_N`, `_eq_N`,
              -- `match_N`, …): `isInternalDetail` is Lean's own authoritative
              -- flag for these — they are proof-irrelevant side artifacts of a
              -- def's body, never human-authored, so not anchors/claims. Still
              -- recurse through their deps so nothing meaningful reachable only
              -- via them is hidden (fail-closed).
              let acc :=
                if n.isInternalDetail then acc
                else acc.push
                  { name := n.toString,
                    module := (moduleNameFor env n).elim "" (·.toString),
                    kind := kindStr info }
              anchorWalkM visited acc (deps.toList ++ rest)

/-- Pending-anchor closure of `topName` in `MetaM`. Returns whether the
top node is a claim (its type is a `Prop`) alongside the closure.
`topName` is pre-visited so it never appears in its own closure; the
seed reuses `constDepsM`, so a claim (or claim wrapper) seeds from its
statement only, a data anchor from type + body. -/
private def anchorClosureM (topName : Name) (topInfo : ConstantInfo) :
    Meta.MetaM (Bool × Array AnchorEntry) := do
  let topIsProp ← Meta.isProp topInfo.type
  let seed ← constDepsM topInfo
  let pending ← anchorWalkM (({} : NameSet).insert topName) #[] seed.toList
  return (topIsProp, pending)

/-- Resolve `fqName`, then return its pending-anchor closure + whether
it is a claim + its module. Runs the `MetaM` walk against the terminal
elaborated environment via `CoreM.toIO'` (mirrors `printAxiomsImpl`). -/
def anchorClosureImpl (p : AnchorClosureParams) :
    RequestM (RequestTask AnchorClosureResp) := do
  let doc ← RequestM.readDoc
  RequestM.mapTaskCostly (lastCmdEnv doc) fun walkResult => do
    match walkResult.env with
    | none =>
        return { found := false,
                 error := some s!"no terminal snapshot: {walkResult.trace}" }
    | some env =>
        let n := parseQualifiedName p.fqName
        match env.find? n with
        | none =>
            return { found := false, error := some s!"constant not found: {p.fqName}" }
        | some info =>
            let coreCtx : Core.Context := { fileName := "", fileMap := default }
            let coreState : Core.State := { env }
            let r ← ((anchorClosureM n info).run').toIO' coreCtx coreState |>.toBaseIO
            match r with
            | .ok (topIsProp, pending) =>
                return {
                  found := true,
                  topKind := kindStr info,
                  topIsProp := topIsProp,
                  topModule := (moduleNameFor env n).elim "" (·.toString),
                  pending := pending
                }
            | .error e =>
                return { found := false, error := some s!"anchor walk failed: {e}" }

/-! ## declInfo

Structured per-declaration facts for the whole open file, straight
from the parsed syntax tree + the elaborated environment. This is the
framework's *syntactic oracle*: every consumer that previously
re-derived declaration structure from source text with regexes
(librarian astslice / inventory / relabel, pipeline signature
extraction) becomes a client of this RPC instead. The recorded bug
family it retires: modifier loss (`noncomputable` under
`noncomputable section` — env truth, not surface text), decl-keyword
prose in comments parsed as declarations (ranges come from the
elaborator, comments have none), and docstring/attr spans drifting
from hand-maintained regex approximations (`DeclarationRanges.range`
covers the full declaration incl. doc comment and attributes).

Two complementary views, joined by position:

  * `commands` — every top-level command in source order with its
    syntax kind and range. Scope reconstruction (namespace stack,
    `variable` blocks in force at a decl, `open X in` prefixes — the
    whole astslice replay engine) is a walk over these kinds, never
    over text. An `open X in <decl>` composite is ONE command
    (kind `Lean.Parser.Command.in`) whose range covers prefix + decl.

  * `decls` — every non-internal constant added by this file, with
    kernel/env facts (kind, `isProp`, `isNoncomputable`, visibility,
    instance status), the pretty-printed signature (section variables
    already incorporated by the elaborator), the docstring, and its
    declaration/selection ranges. `cmdIdx` links each constant to the
    command that declared it (mutual blocks: many decls, one command;
    structures: the inductive plus its projections share a command —
    the primary decl is the one with the earliest selection range).

Positions are `Lean.Position`: 1-based line, 0-based codepoint
column (Python `str` indexing is codepoint-based, so line/col convert
to offsets without UTF-16 mangling). -/

structure DeclInfoParams where
  /-- Pretty-printing signatures costs a `MetaM` pp per decl; callers
  that only need names/ranges/flags can skip it. -/
  includeSignatures : Bool := true
  deriving FromJson, ToJson

instance : RpcEncodable DeclInfoParams := inferInstance

structure SrcRange where
  startLine : Nat
  startCol : Nat
  endLine : Nat
  endCol : Nat
  deriving FromJson, ToJson

structure CmdEntry where
  /-- Full syntax kind, e.g. `Lean.Parser.Command.declaration`. -/
  kind : String
  range : SrcRange
  /-- Label for `namespace` / `end` / `section` commands (first
  identifier argument), else none. -/
  name : Option String := none
  deriving FromJson, ToJson

structure DeclEntry where
  /-- Kernel name as it lives in the env (private decls keep their
  `_private…` mangled form here). -/
  fqName : String
  /-- Private-name-normalized form (what the user wrote, qualified). -/
  userName : String
  kind : String
  isProp : Bool
  isNoncomputable : Bool
  isProtected : Bool
  isPrivate : Bool
  isInstance : Bool
  /-- `ppSignature` output (`<name> <binders> : <type>`), "" when
  skipped or pp failed. Section variables appear as ordinary binders. -/
  signature : String
  docstring : Option String := none
  /-- Index into `commands` of the declaring command. -/
  cmdIdx : Nat
  range : SrcRange
  selection : SrcRange
  deriving FromJson, ToJson

structure DeclInfoResp where
  ok : Bool
  commands : Array CmdEntry := #[]
  decls : Array DeclEntry := #[]
  error : Option String := none
  deriving FromJson, ToJson

instance : RpcEncodable DeclInfoResp := inferInstance

/-- Like `lastCmdEnv`, but accumulates every command's syntax along
the walk. Same snapshot-tree caveats (see the module docstring on the
walker above). -/
structure CmdsWalkResult where
  stxs : Array Syntax := #[]
  env : Option Environment := none
  trace : String

instance : Inhabited CmdsWalkResult := ⟨{ trace := "" }⟩

open Language.Lean in
partial def allCmdsEnv (doc : Server.FileWorker.EditableDocument) :
    ServerTask CmdsWalkResult := Id.run do
  let some headerParsed := doc.initSnap.result?
    | .pure { trace := "initSnap.result? is none (header parse failed)" }
  headerParsed.processedSnap.task.asServerTask.bindCheap fun headerProcessed =>
    Id.run do
      let some headerSuccess := headerProcessed.result?
        | .pure { trace := "headerProcessed.result? is none (import failed)" }
      headerSuccess.firstCmdSnap.task.asServerTask.bindCheap (walk #[])
where
  walk (acc : Array Syntax) (cmd : CommandParsedSnapshot) :
      ServerTask CmdsWalkResult := Id.run do
    let acc := acc.push cmd.stx
    match cmd.nextCmdSnap? with
    | none =>
        cmd.elabSnap.resultSnap.task.asServerTask.bindCheap fun result =>
          .pure { stxs := acc, env := some result.cmdState.env,
                  trace := s!"ok ({acc.size} commands)" }
    | some next =>
        next.task.asServerTask.bindCheap (walk acc)

private def toSrcRange (text : FileMap) (r : Syntax.Range) : SrcRange :=
  let s := text.toPosition r.start
  let e := text.toPosition r.stop
  { startLine := s.line, startCol := s.column,
    endLine := e.line, endCol := e.column }

private def declRangeToSrc (r : DeclarationRange) : SrcRange :=
  { startLine := r.pos.line, startCol := r.pos.column,
    endLine := r.endPos.line, endCol := r.endPos.column }

/-- First identifier among a node's (possibly optional-wrapped) args —
the label of `namespace Foo` / `end Foo` / `section Foo`. One nesting
level is enough for these fixed grammars. -/
private def firstIdent? (stx : Syntax) : Option Name :=
  stx.getArgs.findSome? fun a =>
    if a.isIdent then some a.getId
    else a.getArgs.findSome? fun b =>
      if b.isIdent then some b.getId else none

private def mkCmdEntry (text : FileMap) (stx : Syntax) : CmdEntry :=
  let range := match stx.getRange? with
    | some r => toSrcRange text r
    | none => { startLine := 0, startCol := 0, endLine := 0, endCol := 0 }
  let kind := stx.getKind
  let name :=
    if kind ∈ [``Lean.Parser.Command.namespace, ``Lean.Parser.Command.end,
               ``Lean.Parser.Command.section] then
      (firstIdent? stx).map (·.toString)
    else none
  { kind := kind.toString, range, name }

private def posLE (l₁ c₁ l₂ c₂ : Nat) : Bool :=
  l₁ < l₂ || (l₁ == l₂ && c₁ ≤ c₂)

/-- Index of the command whose range contains `sel`'s start, else the
command count (sentinel; consumers treat out-of-range as "no command",
which cannot happen for decls that came from this file's elaboration). -/
private def findCmdIdx (commands : Array CmdEntry) (sel : SrcRange) : Nat := Id.run do
  for h : i in [0:commands.size] do
    let c := commands[i]
    if posLE c.range.startLine c.range.startCol sel.startLine sel.startCol &&
       posLE sel.startLine sel.startCol c.range.endLine c.range.endCol then
      return i
  return commands.size

/-- Assemble `DeclEntry`s for every non-internal local constant.
`MetaM` for `isProp` / `ppSignature`; per-decl failures degrade that
field rather than failing the whole response (a decl whose pp throws
still reports its ranges and flags). -/
private def declEntriesM (p : DeclInfoParams) (commands : Array CmdEntry) :
    Meta.MetaM (Array DeclEntry) := do
  let env ← getEnv
  let mut out : Array DeclEntry := #[]
  for (n, info) in env.constants.map₂.toList do
    if n.isInternalDetail then
      continue
    let some rs ← Lean.findDeclarationRanges? n
      | continue
    let sig ←
      if p.includeSignatures then
        try
          let f ← PrettyPrinter.ppSignature n
          pure f.fmt.pretty
        catch _ => pure ""
      else pure ""
    let isProp ← try Meta.isProp info.type catch _ => pure false
    let isInst ← try Meta.isInstance n catch _ => pure false
    let doc ← findDocString? env n
    let range := declRangeToSrc rs.range
    let selection := declRangeToSrc rs.selectionRange
    out := out.push {
      fqName := n.toString,
      userName := (privateToUserName? n).getD n |>.toString,
      kind := kindStr info,
      isProp,
      isNoncomputable := Lean.isNoncomputable env n,
      isProtected := Lean.isProtected env n,
      isPrivate := Lean.isPrivateName n,
      isInstance := isInst,
      signature := sig,
      docstring := doc,
      cmdIdx := findCmdIdx commands selection,
      range, selection,
    }
  return out.qsort fun a b =>
    posLE a.range.startLine a.range.startCol b.range.startLine b.range.startCol
      && !(a.range.startLine == b.range.startLine
           && a.range.startCol == b.range.startCol
           && !posLE a.selection.startLine a.selection.startCol
                     b.selection.startLine b.selection.startCol)

def declInfoImpl (p : DeclInfoParams) : RequestM (RequestTask DeclInfoResp) := do
  let doc ← RequestM.readDoc
  let text := doc.meta.text
  RequestM.mapTaskCostly (allCmdsEnv doc) fun walkResult => do
    match walkResult.env with
    | none =>
        return { ok := false,
                 error := some s!"no terminal snapshot: {walkResult.trace}" }
    | some env =>
        let commands := walkResult.stxs.map (mkCmdEntry text)
        let coreCtx : Core.Context := { fileName := "", fileMap := default }
        let coreState : Core.State := { env }
        let r ← ((declEntriesM p commands).run').toIO' coreCtx coreState |>.toBaseIO
        match r with
        | .ok decls => return { ok := true, commands, decls }
        | .error e =>
            return { ok := false, commands,
                     error := some s!"decl walk failed: {e}" }

/-! ## Builtin registration

`builtin_initialize` fires before `main`, in BOTH the watchdog and
worker processes. The actual RPC dispatch happens in the worker
(via `handleRpcCall` in `Lean.Server.Rpc.RequestHandling`); the
watchdog just routes messages. Registering in both is harmless
(the watchdog never invokes `builtinRpcProcedures`). -/
builtin_initialize
  registerBuiltinRpcProcedure
    `Asterism.writeOlean WriteOleanParams WriteOleanResp writeOleanImpl
  registerBuiltinRpcProcedure
    `Asterism.printAxioms PrintAxiomsParams PrintAxiomsResp printAxiomsImpl
  registerBuiltinRpcProcedure
    `Asterism.anchorClosure AnchorClosureParams AnchorClosureResp anchorClosureImpl
  registerBuiltinRpcProcedure
    `Asterism.declInfo DeclInfoParams DeclInfoResp declInfoImpl

end Asterism

/-! ## Main entry — dispatch on argv

`lean --server` runs the watchdog, which spawns child workers via
`lean --worker`. Our binary serves both roles based on argv:

  * `--worker`  → `FileWorker.workerMain` (here is where our builtin
                  RPCs become callable)
  * `--server`  → `Watchdog.watchdogMain`

The watchdog locates the worker binary via env
`LEAN_SERVER_WORKER_PATH` (falls back to argv[0]), so we set that
env var to our binary path in the gateway's `lake serve` startup.
That way: stock `lake serve` watchdog spawns our binary as workers,
which then load this module's `builtin_initialize`. -/
unsafe def main (args : List String) : IO UInt32 := do
  -- Stock `lean.exe`'s C++ entry calls runtime init + search-path init
  -- + `enableInitializerExecution` before handing off to `lean_main`.
  -- Lake's `lean_exe` wrapper calls runtime init but NOT the rest, so
  -- our binary boots with an empty search path and `loadExts := true`
  -- import paths fail. Mirror what lean.exe does. The init APIs are
  -- `unsafe` (they mutate global state), hence the `unsafe def`.
  Lean.initSearchPath (← Lean.findSysroot)
  Lean.enableInitializersExecution
  match args with
  | "--worker" :: _ =>
      Lean.Server.FileWorker.workerMain {}
  | "--server" :: rest =>
      Lean.Server.Watchdog.watchdogMain rest
  | _ =>
      IO.eprintln s!"lean-asterism-server: expected --worker or --server, got {args}"
      return 1
