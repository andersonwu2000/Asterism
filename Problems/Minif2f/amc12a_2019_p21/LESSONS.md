<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `grind` closes small concrete finset power-sum goals (e.g. {2,6,10}) but hits its term-generation limit on 6-element sets like {1,3,5,7,9,11}; fallback: prove `hpow : ∀ n, z^(8*n+1)=z` from `hz8`, expand with `Finset.sum_insert`/`Finset.sum_singleton`, rewrite each `z^(k^2)` via `norm_num; exact hpow N`, then close with `field_simp; ring`.
- For z=(1+Complex.I)/√2 power goals, avoid `ring_nf` then `rw [Complex.I_sq]` directly (leaves unrewritable `Complex.I^3`/`Complex.I^4`); instead prove `z^2 = Complex.I` first via `field_simp` + `rw [(↑√2:ℂ)^2=2]` + `ring_nf` + `rw [Complex.I_sq]` + `ring`, then square that result in a `calc` chain.
