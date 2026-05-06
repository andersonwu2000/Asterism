You just finished `{kind}` on `{slug}` (outcome=`{outcome}`).

`Problems/{problem}/LESSONS.md` (cap={cap}, currently {used}/{cap} bullet lines):

```
{lessons_content}
```

Reflect: did this attempt expose a CROSS-SPAWN learnable signal — something a future agent on a DIFFERENT goal in this problem would benefit from?

Bar — only write if all three:
  - Concrete (names a lemma / API / namespace / goal shape)
  - Non-obvious (a fresh agent would re-discover otherwise)
  - Generalizable beyond this goal

Default is skip. Most reflections should be `skip`.

Restrictions:
  - You may ONLY write to `Problems/{problem}/LESSONS.md`. Do NOT touch any other file.
  - Use the Edit tool. The file contains a `<!-- LESSONS_BEGIN -->` anchor line; insert new lessons immediately AFTER it.

Action:
  - No signal → exit without editing.
  - Signal + cap not full → Edit the file, replace `<!-- LESSONS_BEGIN -->\n` with `<!-- LESSONS_BEGIN -->\n- <one-sentence lesson>\n` (preserving any existing bullet lines after the anchor).
  - Signal + cap full → compare your candidate vs each existing bullet. If strictly stronger than the weakest, Edit the weakest line in place. Otherwise skip.

Reply with one of:
  - `skip`
  - `wrote: <lesson>`
  - `replaced N: <lesson>`  (N = 1-indexed bullet index you replaced)

Time budget: {timeout_min} min. Exit promptly after the Edit (or immediately on `skip`).
