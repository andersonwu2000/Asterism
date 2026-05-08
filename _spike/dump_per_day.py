"""Dump per-day commit list across Hadamard + Asterism."""
import subprocess
from collections import defaultdict


def fetch(repo, name):
    r = subprocess.run(
        ["git", "-C", repo, "log", "--reverse", "--format=%ai|%h|%s"],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    out = []
    for line in r.stdout.strip().splitlines():
        if "|" not in line:
            continue
        ts, h, s = line.split("|", 2)
        out.append((ts.split()[0], name, h, s))
    return out


def main():
    events = fetch("D:/Hadamard", "H") + fetch("D:/Asterism", "A")
    events.sort()
    by_day = defaultdict(list)
    for d, r, h, s in events:
        by_day[d].append((r, h, s))
    for d in sorted(by_day):
        print(f"=== {d} ({len(by_day[d])} commits) ===")
        for r, h, s in by_day[d]:
            print(f"  {r} {h} {s[:160]}")
        print()


if __name__ == "__main__":
    main()
