## Lemma discovery

`## Candidate lemmas` (Context.md) first — pre-searched and `#check`-verified. To find more, Mathlib is at `.lake/packages/mathlib/Mathlib/`; names drift across versions (`pow_le_pow_left` → `pow_le_pow_left₀`), so verify before citing:

- name / notation: Grep over `.lake/packages/mathlib/Mathlib/` (pattern `(theorem|lemma) <name>\b`)
- type pattern: `python -m Tooling.knowledge.loogle '<pattern>'`

## Hard rules

- Do NOT use any name in FORBIDDEN_LEMMAS — anywhere.
- Verify every lemma reference before citing: Grep by name/symbol, loogle by type pattern.
