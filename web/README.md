# Asterism web UI

The browser face of the proving engine: a night-sky reading of the
workspace. Vite + React + TypeScript + Tailwind, self-hosted fonts
(Inter for UI, JetBrains Mono for identifiers, Fraunces for the
display voice). No router/state libraries — a hand-rolled hash router
and one polling hook.

## Screens

- **Board** (`#/`) — the survey sheet. Problems in attention order:
  needs you / in motion / recent / archive; archive namespaces fold
  into cluster rows. `/` focuses the filter.
- **Problem** (`#/problems/<name>`) — the constellation. Goals as
  stars (defs are diamonds, Props circles; proved lights up starlight,
  the live frontier glows accent), strategies as edge bundles,
  frontier focus for big graphs; tabs for Goals / Timeline / Files
  (Manifest renders as a typeset document).
- **Library** (`#/library`) — the atlas. The harvested corpus as one
  sky: each bridged problem a constellation of its real declarations,
  line-art joins only the brightest; search lights matching stars.
- **Inbox** (`#/inbox`) — decisions. Amend requests with word-level
  diffs; ingest sign-offs resolve each anchor/claim to its statement
  (vouching means reading the mathematics).
- **Engine** (`#/telemetry`) — daemon control, live log, usage.

## Development

```
npm install
npm run dev        # http://localhost:5173, proxies /api to :8642
npm run build      # tsc + vite; production is served by FastAPI
npm run lint       # oxlint
npm run smoke      # Playwright suite against a live `asterism serve`
```

The UI is read-only against the engine database; every mutation goes
through the same HTTP chokepoints as the CLI.
