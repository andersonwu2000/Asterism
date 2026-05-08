"""Dump a claude session jsonl as a compact timeline of events."""
import json
import sys
import datetime as dt
from pathlib import Path


def fmt(p: Path) -> None:
    prev_ts = None
    by_msg: dict[str, list] = {}
    for line in p.read_text(encoding='utf-8').splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        ts = (d.get('timestamp') or '')[:19]
        msg = d.get('message', {})
        role = msg.get('role', '')
        ct = msg.get('content', [])
        mid = msg.get('id') or '-'
        if not isinstance(ct, list):
            ct = []
        for c in ct:
            t = c.get('type', '')
            if t in ('thinking', 'tool_use', 'tool_result', 'text'):
                size = (len(c.get('thinking', '')) if t == 'thinking' else
                        len(c.get('text', '')) if t == 'text' else
                        len(str(c.get('content', ''))) if t == 'tool_result'
                        else 0)
                name = c.get('name', '')
                by_msg.setdefault(mid, []).append(
                    (ts, role, t, size, name))
    for mid, events in by_msg.items():
        if not events:
            continue
        ts = events[0][0]
        role = events[0][1]
        gap = ''
        if ts and prev_ts:
            try:
                d0 = dt.datetime.fromisoformat(prev_ts + '+00:00')
                d1 = dt.datetime.fromisoformat(ts + '+00:00')
                sec = (d1 - d0).total_seconds()
                if sec > 30:
                    gap = f'  +{sec:.0f}s'
            except Exception:
                pass
        prev_ts = ts
        parts = []
        for _, _, t, sz, name in events:
            if t == 'thinking':
                parts.append(f'THINK[{sz}]')
            elif t == 'tool_use':
                parts.append(f'tool({name})')
            elif t == 'tool_result':
                parts.append(f'result[{sz}]')
            elif t == 'text':
                parts.append(f'text[{sz}]')
        print(f'{ts} {role[:5]:5s} {" ".join(parts)}{gap}')


if __name__ == '__main__':
    fmt(Path(sys.argv[1]))
