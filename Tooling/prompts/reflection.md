You just finished `{kind}` on `{slug}` (outcome=`{outcome}`).

`Problems/{problem}/LESSONS.md` (cap={cap}, currently {used}/{cap} bullet lines):

```
{lessons_content}
```

Standing Strategist directive for this problem (problem-wide guidance every worker cold-start reads):

```
{directive}
```

If — and ONLY if — that directive makes a CONCRETE claim that this `{outcome}` specifically disproved or showed is the wrong approach (e.g. "lemma X exists / is provable" when you just refuted it), you may retract it: write the one-line reason to `{attempts_dir}/_directive_retract.md`. The framework clears the directive; the Strategist re-issues a corrected one on its next wake (an absent directive beats a wrong one). High bar — "it was just hard" is NOT grounds; when unsure, do not retract.

Reflect: did this attempt expose a CROSS-SPAWN learnable signal — something a future agent on a DIFFERENT goal in this problem would benefit from?

Bar — only write if all three:
  - Concrete (names a lemma / API / namespace / goal shape) — never a framework-internals guess
  - Non-obvious (a fresh agent would re-discover otherwise)
  - Generalizable beyond this goal

Default is skip. Most reflections should be `skip`.

Restrictions:
  - You may write to `Problems/{problem}/LESSONS.md`. Do NOT touch any other file.
  - Use the Edit tool. LESSONS.md contains a `<!-- LESSONS_BEGIN -->` anchor line; insert new lessons immediately AFTER it.

Action:
  - No signal → exit without editing.
  - An existing bullet is now FALSE or misleading in light of this `{outcome}` (e.g. a claim this attempt disproved or showed was the wrong approach) → Edit that bullet to correct it, regardless of the cap. Reply `replaced N: <correction>`.
  - Signal + cap not full → Edit the file, replace `<!-- LESSONS_BEGIN -->\n` with `<!-- LESSONS_BEGIN -->\n- <one-sentence lesson>\n` (preserving any existing bullet lines after the anchor).
  - Signal + cap full → compare your candidate vs each existing bullet. If strictly stronger than the weakest, Edit the weakest line in place. Otherwise skip.

Reply with one of:
  - `skip`
  - `wrote: <lesson>`
  - `replaced N: <lesson>`  (N = 1-indexed bullet index you replaced)

Time budget: {timeout_min} min. Exit promptly after the Edit (or immediately on `skip`).
