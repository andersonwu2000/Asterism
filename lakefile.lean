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

@[default_target]
lean_lib «Library» where
  srcDir := "."
  globs := #[Glob.submodules `Library]
