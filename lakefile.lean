import Lake
open Lake DSL

package «Asterism» where
  leanOptions := #[
    ⟨`pp.unicode.fun, true⟩,
    ⟨`linter.deprecated, true⟩,
    ⟨`weak.linter.mathlibStandardSet, true⟩
  ]

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git"

@[default_target]
lean_lib «Problems» where
  srcDir := "."
  globs := #[Glob.submodules `Problems]

-- F49 — Library/<Topic>/*.lean re-exports proved roots from
-- Problems/, organized by Mathlib-style topic. Each file imports a
-- Problems.<problem>.Root. Empty Library/ glob is harmless.
lean_lib «Library» where
  srcDir := "."
  globs := #[Glob.submodules `Library]

-- Verify-unification (see `docs/dev/verify_unification.md`):
-- custom RPC handlers on the LSP worker so the gateway can write
-- `.olean` and run `#print axioms` in-process instead of paying a
-- fresh `lake build` / `lake env lean` per call.
lean_lib «Asterism» where
  srcDir := "."
  globs := #[Glob.submodules `Asterism]

lean_exe «lean-asterism-server» where
  root := `Asterism.GatewayRpc
  -- Required for the LSP server to be able to load `Init`/`Std`/`Lean`
  -- modules via interpreter-driven imports (see Lean's `IO.getRandomBytes`
  -- and similar `extern` declarations). Without this the worker's
  -- header processing fails with "Could not find native implementation".
  supportInterpreter := true
