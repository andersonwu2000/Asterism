You just finished `{kind}` on `{slug}` (outcome=`{outcome}`).

`Problems/{problem}/LESSONS.md` (cap={cap}, currently {used}/{cap} in use):

```
{lessons_content}
```

Reflect: did this attempt expose a CROSS-SPAWN learnable signal — something a future agent on a DIFFERENT goal in this problem would benefit from?

Bar — only write if all three:
  - Concrete (names a lemma / API / namespace / goal shape)
  - Non-obvious (a fresh agent would re-discover otherwise)
  - Generalizable beyond this goal

Default is skip. Most reflections should be `skip`.

Action:
  - No signal → exit without editing.
  - Signal + cap not full → use Edit tool to append a single line `- <one-sentence lesson>` to `Problems/{problem}/LESSONS.md`.
  - Signal + cap full → compare your candidate vs each existing line. If strictly stronger than the weakest, use Edit tool to replace that line. Otherwise skip.

Reply with one of:
  - `skip`
  - `wrote: <lesson>`
  - `replaced N: <lesson>`  (N = 1-indexed line number you replaced)

Time budget: {timeout_min} min. Exit promptly after the Edit (or immediately on `skip`).
