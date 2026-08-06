"""Seeded-defect probe: does the Adversary's criterion 3 fire on a
planted flaw in the Programme's `## Proof`?

Two defects, both in SG rev 2's Lemma 5, one word apart in flavour:

  D1  the STATEMENT is false — `dst x y = (t - s) * dst p q` (no absolute
      value), justified by the false auxiliary `sqrt (c^2) = c`. Decidable
      mechanically (counterexample at t < s); this is the case the three
      judges asked for a Lean tool to settle.
  D2  the STATEMENT is true — `|t - s|` intact — but the proof silently
      assumes `t - s > 0`, so it covers only half the reals. Pure logic;
      no computation can help, only reading.

If the judge fires on D2 and not D1, the gap is exactly "is this claim
true" rather than "is this argument complete", which is what the
requested tool would close. If it fires on both, hand-checking is
adequate and the requests close.

Nothing touches the live DB: the run works on a copy, and `problem_dir`
is only ever read.

Usage:  python _spike/judge_lean_probe_setup.py     # roll the world back
        python _spike/judge_lean_probe.py {d1|d2|d3|control}

Result: 3/3 caught by criterion 3 (2026-08-02). Adjudication and
the full findings: docs/internal/adjudicated_requests.md.
"""
from __future__ import annotations

import io
import json
import shutil
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path
from types import SimpleNamespace

REPO = Path(r"D:\Asterism")
sys.path.insert(0, str(REPO))

SCRATCH = Path(__file__).resolve().parent  # _spike/; artefacts land beside this file
PROBE_WS = SCRATCH / "probe_ws"
PROBLEM = "sylvester_gallai"
GROUP_ID = 366
BATCH = "b1383b6a"

# --- the seeded edits ------------------------------------------------
# Lemma 5's statement line, its closing line, and the auxiliary fact.
ORIG_STMT = "  `dst x y = |t - s| · dst p q`."
ORIG_TAIL = (
    "  `dst x y = √((t-s)²) · √((p₁-q₁)² + (p₂-q₂)²) = |t-s| · dst p q,`\n"
    "\n"
    "using `√(c²) = |c|`. ∎"
)
ORIG_SINCE = "Since `(t-s)² ≥ 0`,\n`√` is multiplicative on this product:"

D1_STMT = "  `dst x y = (t - s) · dst p q`."
D1_TAIL = (
    "  `dst x y = √((t-s)²) · √((p₁-q₁)² + (p₂-q₂)²) = (t-s) · dst p q,`\n"
    "\n"
    "using `√(c²) = c`. ∎"
)

D2_SINCE = "Since `t - s > 0`,\n`√` is multiplicative on this product:"

# D3 — the shape the judges actually complained about: a corrupted
# monomial buried in a six-variable expansion. `-(q₂-p₂)(r₁-p₁)` really
# contributes `+ q₂p₁`; the seeded text writes `+ q₂p₂` and carries it
# into the collected line, so the two polynomials no longer agree and
# "the six monomials agree term for term" is false. The LEMMA's
# conclusion stays true, so no check of the stated claim can catch this
# — only redoing the expansion term by term, which is exactly what the
# judge said it had to do by hand for six lemmas.
ORIG_L1 = (
    "   `= q₁r₂ - q₁p₂ - p₁r₂ + p₁p₂ - q₂r₁ + q₂p₁ + p₂r₁ - p₂p₁`\n"
    "   `= q₁r₂ - q₁p₂ - p₁r₂ - q₂r₁ + q₂p₁ + p₂r₁,`"
)
D3_L1 = (
    "   `= q₁r₂ - q₁p₂ - p₁r₂ + p₁p₂ - q₂r₁ + q₂p₂ + p₂r₁ - p₂p₁`\n"
    "   `= q₁r₂ - q₁p₂ - p₁r₂ - q₂r₁ + q₂p₂ + p₂r₁,`"
)
D2_TAIL = (
    "  `dst x y = √((t-s)²) · √((p₁-q₁)² + (p₂-q₂)²) = (t-s) · dst p q"
    " = |t-s| · dst p q,`\n"
    "\n"
    "using `√(c²) = c` for `c > 0`. ∎"
)


def seed(body: str, which: str) -> str:
    if which == "control":
        return body
    if which == "d3":
        if ORIG_L1 not in body:
            raise SystemExit(f"anchor not found verbatim:\n{ORIG_L1!r}")
        return body.replace(ORIG_L1, D3_L1)
    for frag in (ORIG_STMT, ORIG_TAIL, ORIG_SINCE):
        if frag not in body:
            raise SystemExit(f"anchor not found verbatim:\n{frag!r}")
    if which == "d1":
        return body.replace(ORIG_STMT, D1_STMT).replace(ORIG_TAIL, D1_TAIL)
    if which == "d2":
        return body.replace(ORIG_SINCE, D2_SINCE).replace(ORIG_TAIL, D2_TAIL)
    raise SystemExit(f"unknown defect {which!r}")


def main() -> int:
    which = (sys.argv[1] if len(sys.argv) > 1 else "d1").lower()

    db_copy = PROBE_WS / "asterism.db"
    if not db_copy.exists():
        raise SystemExit("run judge_lean_probe_setup.py first — no rolled-back workspace")

    # The rolled-back world the judge sees.
    conn = sqlite3.connect(db_copy)
    conn.row_factory = sqlite3.Row
    # The candidate itself comes from the LIVE record (read-only): the
    # rollback deleted rev 2 precisely because it is the thing under
    # judgement, not part of the world.
    live = sqlite3.connect(f"file:{REPO / 'asterism.db'}?mode=ro", uri=True)
    live.row_factory = sqlite3.Row

    row = live.execute(
        "SELECT body FROM programme_revisions"
        " WHERE problem = ? AND rev = 2", (PROBLEM,)).fetchone()
    body = seed(str(row["body"]), which)

    decisions = []
    for d in live.execute(
        "SELECT decision_kind, target_id, brief, reason, payload"
        " FROM strategist_decisions WHERE batch_id LIKE ? ORDER BY id",
        (BATCH + "%",),
    ):
        try:
            payload = json.loads(d["payload"] or "{}")
        except ValueError:
            payload = {}
        decisions.append(SimpleNamespace(
            kind=d["decision_kind"], pipeline=None,
            target_id=d["target_id"], brief=d["brief"], body=None,
            reason=d["reason"], payload=payload))
    if not decisions:
        raise SystemExit(f"no decisions for batch {BATCH}")

    attempts = PROBE_WS / ".attempts" / f"probe-{which}"
    attempts.mkdir(parents=True, exist_ok=True)

    from Tooling.pipeline import adversary

    print(f"[probe] defect={which}  decisions={len(decisions)}  "
          f"body={len(body)}B", flush=True)
    verdict, err, rc = adversary.review(
        round_no=1, attempts_dir=attempts,
        problem_dir=PROBE_WS / "Problems" / PROBLEM,
        conn=conn, problem=PROBLEM, proposal_body=body,
        decisions=decisions, dialogue=[], proof_warn=None,
        group_id=GROUP_ID)

    out = {"defect": which, "rc": rc, "err": err, "verdict": verdict}
    (SCRATCH / f"probe_result_{which}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
