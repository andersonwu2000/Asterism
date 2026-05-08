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

/-- Wait for the worker's snapshot stream to terminate (whole file
elaborated), then call `Lean.writeModule` on the resulting env.
IO errors are captured into `error` rather than surfaced as RPC
failures so the client gets a structured response. -/
def writeOleanImpl (p : WriteOleanParams) : RequestM (RequestTask WriteOleanResp) := do
  let doc ← RequestM.readDoc
  RequestM.mapTaskCostly doc.cmdSnaps.waitAll fun (snaps, _) => do
    match snaps.getLast? with
    | none => return { ok := false, error := some "no snapshots produced" }
    | some snap =>
        let r ← (Lean.writeModule snap.env
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
  RequestM.mapTaskCostly doc.cmdSnaps.waitAll fun (snaps, _) => do
    match snaps.getLast? with
    | none =>
        return { found := false, axioms := #[], error := some "no snapshots produced" }
    | some snap =>
        let n := parseQualifiedName p.fqName
        let env := snap.env
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
def main (args : List String) : IO UInt32 := do
  match args with
  | "--worker" :: _ =>
      Lean.Server.FileWorker.workerMain {}
  | "--server" :: rest =>
      Lean.Server.Watchdog.watchdogMain rest
  | _ =>
      IO.eprintln s!"lean-asterism-server: expected --worker or --server, got {args}"
      return 1
