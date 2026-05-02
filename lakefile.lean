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
