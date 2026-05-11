"""Audit our 20 imported miniF2F problems against the v2c "fixed" dataset.
v2c-different statement => paper authors deemed it broken in original.
"""
import json
import re
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def strip_signature_only(formal_stmt: str) -> str:
    """v2c gives full theorem header. Strip to just hypotheses + conclusion."""
    # remove `theorem <name>` prefix
    s = re.sub(r"^theorem\s+\S+\s*", "", formal_stmt.strip())
    # remove `:= by ...` or trailing `:= by sorry`
    s = re.sub(r"\s*:=\s*by.*$", "", s, flags=re.DOTALL)
    return normalize(s)


our_problems = {}
for pdir in sorted(Path("Problems/Minif2f").iterdir()):
    if not pdir.is_dir():
        continue
    mfst = pdir / "Manifest.md"
    if not mfst.exists():
        continue
    text = mfst.read_text(encoding="utf-8")
    parts = text.split("## Statement")
    if len(parts) < 2:
        continue
    stmt_section = parts[1].split("##")[0].strip()
    our_problems[pdir.name] = stmt_section

# v2c dataset from arxiv 2511.03108 (Nov 2025) — paper authors' fixed
# version. Download from:
#   https://raw.githubusercontent.com/roozbeh-yz/miniF2F_v2/main/datasets/miniF2F_v2c.jsonl
# Place at docs/errata/minif2f/v2c.jsonl (not committed — too large).
v2c = {}
with open("docs/errata/minif2f/v2c.jsonl", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        v2c[d["name"]] = d.get("formal_statement", "")

overlap = sorted(set(our_problems) & set(v2c))
missing = [n for n in our_problems if n not in v2c]

print(f"# Audit: ours = {len(our_problems)}, v2c = {len(v2c)}, "
      f"overlap = {len(overlap)}\n")

if missing:
    print(f"Not in v2c ({len(missing)}):")
    for n in missing:
        print(f"  - {n}")
    print()

DIFFER_FLAG = []
for name in overlap:
    ours_n = normalize(our_problems[name])
    v2c_n = strip_signature_only(v2c[name])
    # Heuristic match: did v2c keep similar statement, or rewrite?
    # Count token-set Jaccard.
    def toks(s):
        return set(re.findall(r"\b\w+\b|[≥≤≠∀∃∈∑]", s))
    ts1, ts2 = toks(ours_n), toks(v2c_n)
    sim = len(ts1 & ts2) / max(len(ts1 | ts2), 1)
    print(f"=== {name} (token-Jaccard {sim:.2f}) ===")
    print(f"  OURS: {ours_n[:250]}")
    print(f"  V2C : {v2c_n[:250]}")
    if sim < 0.65:
        DIFFER_FLAG.append((name, sim))
    print()

print(f"\n## High-difference candidates (likely v2c rewrote / fixed):")
for n, s in sorted(DIFFER_FLAG, key=lambda x: x[1]):
    print(f"  {n}  (sim={s:.2f})")
