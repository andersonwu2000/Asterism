# PutnamBench Phase 1 — prepared batch

Upstream: trishullab/PutnamBench @ a23d8e6 (toolchain there: v4.27.0; ours: see lean-toolchain).
Selected: **50** problems (25 with official solution filled in Defs.lean, 25 pure proof).
Excluded for toolchain incompatibility: 0 (statements never edited — excluded, not fixed).

| stratum | problems |
|---|---|
| A1 | putnam_1962_a1, putnam_1977_a1, putnam_1994_a1, putnam_2011_a1, putnam_2025_a1 |
| A2 | putnam_1962_a2, putnam_1980_a2, putnam_2005_a2, putnam_2025_a2 |
| A3 | putnam_1962_a3, putnam_1983_a3, putnam_2005_a3, putnam_2025_a3 |
| A4 | putnam_1962_a4, putnam_1982_a4, putnam_2005_a4, putnam_2025_a4 |
| A5 | putnam_1962_a5, putnam_1986_a5, putnam_2005_a5, putnam_2025_a5 |
| A6 | putnam_1962_a6, putnam_1983_a6, putnam_2002_a6, putnam_2025_a6 |
| B1 | putnam_1962_b1, putnam_1976_b1, putnam_1994_b1, putnam_2010_b1, putnam_2025_b1 |
| B2 | putnam_1962_b2, putnam_1982_b2, putnam_2004_b2, putnam_2025_b2 |
| B3 | putnam_1962_b3, putnam_1982_b3, putnam_2005_b3, putnam_2025_b3 |
| B4 | putnam_1964_b4, putnam_1988_b4, putnam_2007_b4, putnam_2025_b4 |
| B5 | putnam_1962_b5, putnam_1983_b5, putnam_2004_b5, putnam_2025_b5 |
| B6 | putnam_1962_b6, putnam_1983_b6, putnam_2005_b6, putnam_2025_b6 |

## Firing the run (operator)

```
asterism run --scope 'Putnam.%'
```

G0 gate (ROADMAP): ≥40% proved of 50 → full 270-problem Phase 2.
