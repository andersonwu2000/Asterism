- **Integer scalar multiplication of one in ZMod**: Split via `zsmul_eq_mul` (rewrites `k • 1` to `↑k * 1`) then `mul_one`; chain with `.trans`.

- **`ofAdd ∘ toAdd` round-trip identity**: Reduce via injectivity of `toAdd`, then close with the `toAdd ∘ ofAdd = id` direction which holds by `rfl`/simp.

- **zpow equals ofAdd of zsmul on Multiplicative**: Use `toAdd` as pivot: prove `toAdd (x^k) = k • a` via `Multiplicative.toAdd_zpow`, then reconstruct with `ofAdd_toAdd` round-trip; combine with `rw`.

- **ZMod natCast val round-trip**: Avoid ring metavariables by routing through `ZMod.val`: use `ZMod.val_natCast` + `Nat.mod_eq_of_lt` for ℕ arithmetic, then close with `ZMod.val`-injectivity via `Fin.ext`.

- **ZMod val round-trip through ℤ**: Factor `ℕ→ℤ→ZMod` into two steps: `Int.cast_natCast` (simp) collapses the ℤ layer, then `ZMod.natCast_val` (needs `NeZero` from `Fact`) closes with `h1.trans h2`.

- **Multiplicative zpowers membership via ZMod witness**: Witness `k := (toAdd x).val`; chain `toAdd_zpow` + `zsmul_eq_mul` + ZMod val cast round-trip; close `ofAdd (toAdd x) = x` by `rfl`.
