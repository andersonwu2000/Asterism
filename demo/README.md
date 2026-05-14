# Demo layout — live visualization during a framework run

Six fixed files under `demo/active/` are kept in sync with the
framework's live state. VS Code is configured once with six panes
pinned to these files; `watcher.py` updates the disk content; VS Code's
auto-revert refreshes the panes.

## Layout

```
┌──────────────┬──────────────────┬──────────────┐
│  worker 1    │                  │  worker 2    │
│ (active .lean│    TREE.md       │ (active .lean│
│  in spawn)   │                  │  in spawn)   │
├──────────────┼──────────────────┼──────────────┤
│  worker 3    │     stats        │  worker 4    │
│ (active .lean│  wall-clock /    │ (active .lean│
│              │  goals / spawns  │              │
└──────────────┴──────────────────┴──────────────┘
```

Centre column is roughly 1.5–2× the width of side columns.

## Files maintained by `watcher.py`

| File | Contents |
|---|---|
| `active/worker_{1..4}.lean` | Copy of each spawn sandbox's most-recent `.lean`; refreshed every poll |
| `active/tree.md` | Copy of `Problems/<problem>/TREE.md`; refreshed every poll |
| `active/stats.md` | Generated panel: wall clock, goal counts, strategy counts, per-worker file paths |

## Usage

Set up the VS Code layout once:

1. Open the repo in VS Code.
2. `View → Editor Layout → Grid (2×3)` or equivalent — split into 3 columns × 2 rows.
3. In each pane, `File → Open → demo/active/<file>` for the corresponding file.
4. Settings → Files: Auto Save = `afterDelay`; Files: Auto Reveal Exclude = (clear if set).
5. Drag the centre column edges to make it wider than the sides.

Start the watcher alongside the daemon:

```bash
# Terminal 1 — the framework
asterism run --scope sl2_v_n_irreducible

# Terminal 2 — the demo feeder
python demo/watcher.py --problem sl2_v_n_irreducible
```

Stop the watcher with Ctrl+C; the active/ files remain on disk so the
VS Code panes don't flash to empty between demo takes.

## Notes

- Spawns whose sandbox hasn't been touched in 60s are considered idle
  and stop occupying worker panes. The pane keeps its last-seen content
  rather than clearing.
- `_dedupe_check_*.lean` files that live directly under `.attempts/`
  (not in any spawn sandbox) are intentionally skipped.
- If you want raster-style "matrix rain" feel, increase the daemon's
  worker pool (`gateway.workers` in `Asterism.yaml`) and use a tighter
  watcher interval (`--interval 0.5`).
- The poll-and-copy approach trades a tiny amount of latency (≤ 1s
  default) for full disk-mediated decoupling: VS Code never reads from
  the spawn sandbox directly, so even if a spawn ends mid-display the
  pane simply stops updating, never erroring.
