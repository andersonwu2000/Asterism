"""SQLite storage: one accounts database for the server, one database per project.

Only the server process writes while it runs (the admin command creates a project's database
before or beside it; SQLite's own locking keeps that safe). The server touches the databases only
from its event loop thread, so each domain function, having no await inside, runs as one unit.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from . import util

ACCOUNTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    github_id TEXT NOT NULL UNIQUE,
    github_login TEXT NOT NULL,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS web_sessions (
    digest TEXT PRIMARY KEY,
    person_id INTEGER NOT NULL,
    created REAL NOT NULL,
    expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS login_states (
    digest TEXT PRIMARY KEY,
    next TEXT NOT NULL,
    expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS device_requests (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL,
    device_digest TEXT NOT NULL UNIQUE,
    user_digest TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    computer TEXT NOT NULL,
    created REAL NOT NULL,
    expires REAL NOT NULL,
    status TEXT NOT NULL,          -- pending, approved, denied, issued
    person_id INTEGER
);
CREATE TABLE IF NOT EXISTS oauth_clients (
    client_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    redirect_uris TEXT NOT NULL,   -- JSON list
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_codes (
    digest TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    person_id INTEGER NOT NULL,
    slug TEXT NOT NULL,
    challenge TEXT NOT NULL,
    expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_tokens (
    digest TEXT PRIMARY KEY,
    kind TEXT NOT NULL,            -- access, refresh
    client_id TEXT NOT NULL,
    person_id INTEGER NOT NULL,
    slug TEXT NOT NULL,
    credential_id INTEGER NOT NULL,
    expires REAL NOT NULL
);
"""

PROJECT_SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    repo TEXT NOT NULL,
    owner_login TEXT NOT NULL,     -- the GitHub login that becomes the owner on first sign-in
    owner_person INTEGER,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS people (
    person_id INTEGER PRIMARY KEY, -- id in the accounts database
    name TEXT NOT NULL UNIQUE,
    joined REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,            -- default, ownership, custom
    permissions TEXT NOT NULL,     -- JSON list
    owner_person INTEGER,          -- ownership groups only
    others_mention INTEGER NOT NULL DEFAULT 0,
    others_channel INTEGER NOT NULL DEFAULT 0,
    others_assign INTEGER NOT NULL DEFAULT 0,
    others_regroup INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS group_members (
    group_id INTEGER NOT NULL,
    member_kind TEXT NOT NULL,     -- person, agent
    member_id INTEGER NOT NULL,
    PRIMARY KEY (group_id, member_kind, member_id)
);
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    person_id INTEGER NOT NULL,
    kind TEXT NOT NULL,            -- claude-code, codex, chatgpt
    created REAL NOT NULL,
    session TEXT,                  -- the bound session, NULL when none
    credential_id INTEGER,         -- the credential the bound session came through
    generation INTEGER NOT NULL DEFAULT 0,
    last_session TEXT,             -- the last session ever bound; a different one raises the generation
    last_active REAL,
    last_poll REAL,                -- start or end of the latest presence poll of the bound session
    offline_reason TEXT,           -- unanswered or silent: held offline until its session calls a tool
    announced INTEGER,             -- the presence last announced in #general (1 online, 0 offline, NULL never)
    last_tool REAL                 -- the latest call of an agent endpoint other than poll and ack
);
CREATE UNIQUE INDEX IF NOT EXISTS agents_session ON agents(person_id, session) WHERE session IS NOT NULL;
CREATE TABLE IF NOT EXISTS superseded (
    person_id INTEGER NOT NULL,
    session TEXT NOT NULL,
    agent_id INTEGER NOT NULL,
    at REAL NOT NULL,
    PRIMARY KEY (person_id, session)
);
CREATE TABLE IF NOT EXISTS invites (
    digest TEXT PRIMARY KEY,
    github_login TEXT,
    created_by INTEGER NOT NULL,
    created REAL NOT NULL,
    expires REAL NOT NULL,
    used_by INTEGER,
    used REAL
);
CREATE TABLE IF NOT EXISTS credentials (
    id INTEGER PRIMARY KEY,
    digest TEXT NOT NULL UNIQUE,
    person_id INTEGER NOT NULL,
    kind TEXT NOT NULL,            -- computer, connector
    label TEXT NOT NULL,
    created REAL NOT NULL,
    last_used REAL,
    revoked REAL,
    via TEXT,                      -- how it was issued: invite, device, connector
    last_poll REAL,                -- start or end of the latest computer poll with this credential
    connected INTEGER              -- the computer connection last written to the log (1 connected, 0 or NULL not)
);
CREATE TABLE IF NOT EXISTS agent_invites (
    digest TEXT PRIMARY KEY,       -- digest of the code in the link; the code itself is never kept
    person_id INTEGER NOT NULL,    -- the inviting member; the computer is authorised in their name
    created REAL NOT NULL,
    expires REAL NOT NULL,
    used REAL,
    credential_id INTEGER,         -- the credential the link was redeemed with (new or existing)
    computer TEXT,
    product TEXT
);
CREATE TABLE IF NOT EXISTS computer_sessions (
    credential_id INTEGER NOT NULL, -- the local sessions a computer's program reported it can wake right now
    session TEXT NOT NULL,          -- namespaced like agents.session: 'local:<id>'
    product TEXT NOT NULL,          -- claude-code, codex
    PRIMARY KEY (credential_id, session)
);
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,     -- without the '#'
    created_by INTEGER,            -- person id; NULL for #general
    created REAL NOT NULL
);
INSERT OR IGNORE INTO channels (name, created) VALUES ('general', CAST(strftime('%s', 'now') AS REAL));
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    place TEXT NOT NULL,           -- '#name' for a channel; 'p:<kind>:<id>|<kind>:<id>' (sorted) for a private one
    sender_kind TEXT NOT NULL,     -- person, agent, system
    sender_id INTEGER,
    sender_person INTEGER,         -- the person behind the sender (itself for a person)
    sender_name TEXT NOT NULL,
    text TEXT NOT NULL,
    reply_to INTEGER,
    hop INTEGER NOT NULL,
    mentions TEXT NOT NULL,        -- JSON list of the member and group names mentioned
    sent REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_place ON messages(place, id);
CREATE INDEX IF NOT EXISTS messages_speaker ON messages(sender_kind, sender_id, place, sent);
CREATE TABLE IF NOT EXISTS levels (
    message_id INTEGER NOT NULL,   -- one row per reader, written when the message is sent
    reader_kind TEXT NOT NULL,     -- person, agent
    reader_id INTEGER NOT NULL,
    level TEXT NOT NULL,           -- important, normal, muted
    seen REAL,                     -- an agent was handed the whole message by `messages`
    PRIMARY KEY (reader_kind, reader_id, message_id)
);
CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY,
    agent_id INTEGER NOT NULL,
    kind TEXT NOT NULL,            -- message, notice, or reminder (message_id: the message it is about)
    message_id INTEGER,
    state TEXT NOT NULL,           -- pending, out (handed out, not acknowledged), done, dropped
    how TEXT NOT NULL,             -- what an acknowledgement counts as: push, or return (held while offline)
    created REAL NOT NULL,
    handed_out REAL,
    attempts INTEGER NOT NULL DEFAULT 0,
    done REAL
);
CREATE INDEX IF NOT EXISTS deliveries_open ON deliveries(agent_id, state);
CREATE INDEX IF NOT EXISTS deliveries_message ON deliveries(agent_id, message_id);
CREATE TABLE IF NOT EXISTS reads (
    reader_kind TEXT NOT NULL,
    reader_id INTEGER NOT NULL,
    place TEXT NOT NULL,
    upto INTEGER NOT NULL,
    PRIMARY KEY (reader_kind, reader_id, place)
);
CREATE TABLE IF NOT EXISTS mutes (
    member_kind TEXT NOT NULL,     -- a row means: messages without a mention of the member are muted here
    member_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    PRIMARY KEY (member_kind, member_id, channel)
);
CREATE TABLE IF NOT EXISTS followups (
    agent_id INTEGER NOT NULL,     -- an important message handed over to an agent and not yet answered
    message_id INTEGER NOT NULL,
    handed REAL NOT NULL,
    period REAL NOT NULL,          -- start of the current reminder period
    due REAL,                      -- when the next reminder (or the silence check) falls due; NULL when answered
    reminders INTEGER NOT NULL DEFAULT 0,
    answered REAL,
    PRIMARY KEY (agent_id, message_id)
);
CREATE INDEX IF NOT EXISTS followups_due ON followups(due) WHERE answered IS NULL;
CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,           -- sub_<digest of person, callback, event, arguments>
    agent_id INTEGER NOT NULL,
    person_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    arguments TEXT NOT NULL,       -- JSON object
    secret TEXT NOT NULL,          -- whsec_...: kept in clear to sign; never logged
    old_secret TEXT,               -- the previous secret, also signed with until old_until
    old_until REAL,
    expires REAL NOT NULL,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS subscriptions_agent ON subscriptions(agent_id, expires);
CREATE TABLE IF NOT EXISTS chain_reminders (
    agent_id INTEGER NOT NULL,     -- the agent was reminded once about replying to this message
    reply_to INTEGER NOT NULL,
    PRIMARY KEY (agent_id, reply_to)
);
"""


# Columns added after a table first shipped: a database made by an earlier version gets them when opened.
# The optional third item fills the new column of the rows that existed before (an SQL expression).
ADDED_COLUMNS = {
    "agents": [("offline_reason", "TEXT"), ("announced", "INTEGER"), ("last_tool", "REAL")],
    "credentials": [("via", "TEXT", "CASE kind WHEN 'connector' THEN 'connector' ELSE 'device' END"),
                    ("last_poll", "REAL"), ("connected", "INTEGER")],
}


def _upgrade(conn: sqlite3.Connection) -> None:
    for table, cols in ADDED_COLUMNS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not have:
            continue
        for name, kind, *fill in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
                if fill:
                    conn.execute(f"UPDATE {table} SET {name} = {fill[0]}")
    conn.commit()


def _open(path: Path, schema: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema)
    if schema is PROJECT_SCHEMA:
        _upgrade(conn)
    return conn


class Store:
    def __init__(self, data: Path):
        self.data = data
        self.projects_dir = data / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._accounts: sqlite3.Connection | None = None
        self._projects: dict[str, sqlite3.Connection] = {}

    def accounts(self) -> sqlite3.Connection:
        if self._accounts is None:
            self._accounts = _open(self.data / "accounts.db", ACCOUNTS_SCHEMA)
        return self._accounts

    def project_path(self, slug: str) -> Path:
        return self.projects_dir / f"{slug}.db"

    def project(self, slug: str) -> sqlite3.Connection | None:
        """The project's database, or None. A project exists once its file does (the admin
        command creates it under a temporary name and renames it when complete)."""
        if not util.valid_slug(slug):
            return None
        conn = self._projects.get(slug)
        if conn is None:
            path = self.project_path(slug)
            if not path.is_file():
                return None
            conn = self._projects[slug] = _open(path, PROJECT_SCHEMA)
        return conn

    def slugs(self) -> list[str]:
        return sorted(p.stem for p in self.projects_dir.glob("*.db") if util.valid_slug(p.stem))

    def new_project_db(self, slug: str) -> tuple[sqlite3.Connection, Path]:
        tmp = self.projects_dir / f".{slug}.db.part"
        if tmp.exists():
            tmp.unlink()
        return _open(tmp, PROJECT_SCHEMA), tmp

    def publish_project_db(self, conn: sqlite3.Connection, tmp: Path, slug: str) -> None:
        conn.commit()
        conn.close()
        os.replace(tmp, self.project_path(slug))

    def close(self) -> None:
        for c in [self._accounts, *self._projects.values()]:
            if c is not None:
                c.close()
        self._accounts, self._projects = None, {}
