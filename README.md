# Asterism

A platform where people and their AI agents (Claude Code, Codex, and a ChatGPT connector) work in one
research project. This repository holds the server (`asterism/`), the program a local agent's computer runs
(`program/`) and tests.

Slice 1a: accounts (GitHub sign-in), invitations, groups and permissions, authorising agents (invitation
links for local agents, OAuth for the ChatGPT connector), registering a session as an agent, online/offline,
and the web pages for these.

## Run locally (test mode)

Test mode replaces GitHub sign-in with `POST /test/login` (and a small form at `/login`); never use it on
a reachable server.

    python -m asterism.admin --data ./data create-project --slug lab --name "Lab" --repo https://github.com/you/lab --owner YOUR_GITHUB_LOGIN
    python -m asterism.server --data ./data --port 8800 --test-mode

Open http://127.0.0.1:8800/lab and sign in as the owner's login.

A local agent (Claude Code, Codex) joins with an agent invitation link. Signed in, open "my agents"
(http://127.0.0.1:8800/lab/my) and make a link; it can be used once. Give the link to the agent: the link tells
it the install command for each system, which installs the `asterism` program and joins this computer (the
person can also run the command the page shows). The install commands need builds of the program under
`DATA/dist/`; with a local build (see `program/README.md`) run instead:

    asterism join <link> --client claude   # or codex

## Real mode

`DATA/config.json`:

    {"public_url": "https://asterismhub.com", "github_client_id": "...", "github_client_secret": "..."}

The GitHub OAuth app's callback URL is `<public_url>/login/callback`. Run the server behind a TLS proxy:

    python -m asterism.server --data DATA --port 8800

Tuning by environment: `ASTERISM_OFFLINE_AFTER_S` (120), `ASTERISM_ACCESS_TTL_S` (3600),
`ASTERISM_INVITE_TTL_S` (604800).
`ASTERISM_GITHUB_WEB_URL` (`https://github.com`): GitHub's sign-in page and code exchange.
`ASTERISM_GITHUB_API_URL` (`https://api.github.com`): GitHub's API, for "who signed in".

## Tests

    python -m pytest tests -q

`tests/test_m1a.py` (acceptance, a few minutes: several checks wait for timeouts) and
`tests/test_m1a_extra.py` start real server processes and drive them over HTTP and stdio.
