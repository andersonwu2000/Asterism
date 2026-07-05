# Paper index

Read `__TEXT_PATH__` — normalized paper text; `## p.N` headings are page anchors.

Write `__MAP_PATH__` — a navigation map, NOT a summary:

```markdown
## Structure
- [p.N–M] <theorem|definition|lemma|section> <label as printed>: <exact title/name>

## Dependencies
- <label> ← <internal labels its proof/statement uses>

## Notation
- `<symbol/term>`: <meaning> [p.N]
```

Rules:
- Locations must be real `p.N` anchors from the text.
- No content summaries, no proof sketches — statements stay in the original; the map only says WHERE.
- Notation: paper-specific only.
- Total under __TARGET_CHARS__ characters.
