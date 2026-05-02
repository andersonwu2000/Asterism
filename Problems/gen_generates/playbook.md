- **Integer scalar multiplication of one in ZMod**: Split via `zsmul_eq_mul` (rewrites `k • 1` to `↑k * 1`) then `mul_one`; chain with `.trans`.

- **`ofAdd ∘ toAdd` round-trip identity**: Reduce via injectivity of `toAdd`, then close with the `toAdd ∘ ofAdd = id` direction which holds by `rfl`/simp.

- **zpow equals ofAdd of zsmul on Multiplicative**: Use `toAdd` as pivot: prove `toAdd (x^k) = k • a` via `Multiplicative.toAdd_zpow`, then reconstruct with `ofAdd_toAdd` round-trip; combine with `rw`.
