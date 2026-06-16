"""decision_log.md terseness guard — keep entries readable a month later.

`docs/internal/decision_log.md` is the framework's design-decision log. Its
editing principle (stated at the top of that file): each entry is one or two
PLAIN sentences saying "what was wrong, what changed". Mechanism detail
(function names, code paths, DB columns) belongs in the commit message /
`git log`, not here — an entry that dumps it becomes a wall of text you can no
longer skim, which defeats the whole point of the log.

This test enforces that principle mechanically with a per-LINE character cap
(字數, i.e. Unicode code points — a CJK character counts as one). An entry that
genuinely needs more room should split into a short headline plus indented
sub-bullets (each line under the cap), not grow into one long line.

The log lives under docs/internal/ which is gitignored (operator-local), so it
is simply absent on CI checkouts. The test SKIPS when the file isn't present
and acts as a local lint when it is — exactly the behaviour we want for an
operator-local doc.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "internal" / "decision_log.md"

# One-to-two plain sentences plus the `- <hash> — **headline**:` prefix sit
# well under this; the readable early entries top out around 165 chars. Past
# this you're dumping detail that belongs in the commit message — trim, or
# split into a headline + indented sub-bullets. Raise this number only
# together with a matching edit to the editing principle at the top of
# decision_log.md (so the doc and the guard never disagree).
_MAX_LINE = 200

# Shown verbatim on failure so the operator is reminded HOW to write entries,
# not just THAT a line is too long. Mirrors the blockquote in decision_log.md.
_PRINCIPLE = (
    "decision_log 編輯原則:每條用白話寫「問題是什麼、改了什麼」一兩句、讓一個月後也一眼看懂;"
    "函式名 / 機制細節留給 commit message / git log,別放這。"
    f"每行 ≤ {_MAX_LINE} 字,要更多空間就拆成短標題 + 縮排子項,別讓一行長成一整段。"
)


def test_decision_log_lines_stay_terse() -> None:
    if not LOG.exists():
        pytest.skip(
            "docs/internal/decision_log.md is gitignored (operator-local) and "
            "absent here — terseness guard only runs where the log exists")
    over = [
        f"  L{i}: {len(line)} 字 (> {_MAX_LINE}) — {line[:48]}…"
        for i, line in enumerate(
            LOG.read_text(encoding="utf-8").splitlines(), 1)
        if len(line) > _MAX_LINE
    ]
    assert not over, (
        "decision_log.md 有行超過字數上限:\n"
        + "\n".join(over)
        + "\n\n"
        + _PRINCIPLE)
