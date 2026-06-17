"""decision_log.md terseness guard — keep entries readable a month later.

`docs/internal/decision_log.md` is the framework's design-decision log. Its
editing principle (stated at the top of that file): each ENTRY is one or two
PLAIN sentences saying "what was wrong, what changed". Mechanism detail
(function names, code paths, DB columns) belongs in the commit message /
`git log`, not here — an entry that dumps it becomes a wall of text you can no
longer skim, which defeats the whole point of the log.

This test enforces that principle mechanically with a per-ENTRY character cap
(字數, i.e. Unicode code points — a CJK character counts as one). The unit is
the ENTRY (the text between two top-level `- ` bullets), NOT the line: wrapping
a long entry across several lines doesn't make it terser, so the cap is on the
entry's total text. An entry that genuinely needs more room should be trimmed
(push detail to the commit message), not split.

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

# A genuinely terse entry — `- <hash> (<date>) — **headline**: one or two
# plain clauses — sits under this. Past it you're dumping detail that belongs
# in the commit message / git log; trim. Raise this number only together with
# a matching edit to the editing principle at the top of decision_log.md (so
# the doc and the guard never disagree).
_MAX_ENTRY = 200


def _entries(text: str) -> "list[list[str]]":
    """Split the log body into entries. An entry starts at a top-level `- `
    bullet and runs through any indented continuation lines, up to the next
    `- ` / blank line / section marker (`#`, `---`, `>`)."""
    out: "list[list[str]]" = []
    cur: "list[str] | None" = None
    for ln in text.splitlines():
        if ln.startswith("- "):
            if cur is not None:
                out.append(cur)
            cur = [ln]
        elif cur is not None:
            if ln.strip() == "" or ln.startswith(("#", "---", ">")):
                out.append(cur)
                cur = None
            else:
                cur.append(ln)            # indented continuation
    if cur is not None:
        out.append(cur)
    return out


def _entry_chars(entry: "list[str]") -> int:
    """Code points of the entry's text between the two `-` bullets (leading
    `- ` marker + per-line indentation stripped)."""
    parts = []
    for i, ln in enumerate(entry):
        s = ln.strip()
        if i == 0 and s.startswith("- "):
            s = s[2:]
        parts.append(s)
    return len("".join(parts))


# Shown verbatim on failure so the operator is reminded HOW to write entries,
# not just THAT one is too long. Mirrors the blockquote in decision_log.md.
_PRINCIPLE = (
    "decision_log 編輯原則:每條(兩個 - 之間)用白話寫「問題是什麼、改了什麼」一兩句、"
    "讓一個月後也一眼看懂;函式名 / 機制細節留給 commit message / git log,別放這。"
    f"每條 ≤ {_MAX_ENTRY} 字,超了就 trim(把細節推到 commit message),別讓一條長成一整段。"
)


def test_decision_log_entries_stay_terse() -> None:
    if not LOG.exists():
        pytest.skip(
            "docs/internal/decision_log.md is gitignored (operator-local) and "
            "absent here — terseness guard only runs where the log exists")
    over = [
        f"  {_entry_chars(e)} 字 (> {_MAX_ENTRY}) — {e[0][:54]}…"
        for e in _entries(LOG.read_text(encoding="utf-8"))
        if _entry_chars(e) > _MAX_ENTRY
    ]
    assert not over, (
        "decision_log.md 有 entry 超過字數上限:\n"
        + "\n".join(over)
        + "\n\n"
        + _PRINCIPLE)
