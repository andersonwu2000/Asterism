"""SQLite storage: one accounts database for the server, one database per project.

Only the server process writes while it runs (the admin command creates a project's database
before or beside it; SQLite's own locking keeps that safe). The server touches the databases only
from its event loop thread, so each domain function, having no await inside, runs as one unit.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable

from . import util

ACCOUNTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    github_id TEXT NOT NULL UNIQUE,
    github_login TEXT NOT NULL,
    created REAL NOT NULL,
    locale TEXT,                   -- the language the person chose for the pages; NULL: the browser's
    writer TEXT                    -- the machine id of the computer the person chose to write the repositories' files
                                   -- with its own git, in every project (w3); NULL: the server writes, with the
                                   -- person's GitHub token
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
CREATE TABLE IF NOT EXISTS github_tokens (
    person_id INTEGER PRIMARY KEY, -- a person's GitHub authorization, kept to save repository files in their name (1w)
    token TEXT NOT NULL,           -- the access token, encrypted (usertokens.py); never logged or returned
    expires REAL,                  -- when it expires; NULL: it does not
    refresh TEXT,                  -- the refresh token, encrypted; NULL: none was given
    refresh_expires REAL,          -- when the refresh token expires; NULL: unknown or never
    created REAL NOT NULL,         -- when it was given (sign-in) or last refreshed
    refused REAL                   -- GitHub refused it then (and no refresh helped): the person signs in again
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
    created REAL NOT NULL,
    notice_channel INTEGER         -- the channel (id) the system's notices go to; NULL: the first channel
);
CREATE TABLE IF NOT EXISTS people (
    person_id INTEGER PRIMARY KEY, -- id in the accounts database
    name TEXT NOT NULL UNIQUE,
    joined REAL NOT NULL,
    last_beat REAL,                -- the latest beat of an open page of the project (presence); NULL never
    status_title TEXT NOT NULL DEFAULT '', -- the person's status in this project (1s): one line, 0 to 200 characters
    status_at REAL                 -- when it last changed; NULL: never
);
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,            -- default, ownership, custom
    permissions TEXT NOT NULL,     -- JSON list; an ownership group's: what others may do with its person's agents
    owner_person INTEGER,          -- ownership groups only
    created REAL NOT NULL,
    position INTEGER,              -- the order of the non-default groups (lower is higher); NULL for default groups
    separate INTEGER NOT NULL DEFAULT 0   -- 1: its online members are a section of their own in the member list
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
    last_tool REAL,                -- the latest call of an agent endpoint other than poll and ack
    quiet_since REAL,              -- its session left its computer's list then; going offline not announced yet
    model TEXT,                    -- the model its session last said it runs on (X-Asterism-Model); NULL: unknown
    status_title TEXT NOT NULL DEFAULT '', -- its status (1s), written by itself: one line, 0 to 200 characters
    status_body TEXT NOT NULL DEFAULT '',  -- 0 to 10,000 characters, kept as written; empty when the title is
    status_at REAL,                -- when the agent last set it (set_status), changed or not; NULL: never
    update_every_h INTEGER,        -- its person wants the status updated at least this often (hours); NULL: not asked
    update_every_at REAL,          -- when update_every_h was last set
    status_reminded REAL           -- when it was last reminded of an update due (statuses.UPDATE_DUE)
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
    connected INTEGER,             -- the computer connection last written to the log (1 connected, 0 or NULL not)
    quotas TEXT,                   -- a computer's: the quotas its program last reported (JSON list, computers.QUOTAS);
                                   -- shown to its person only. NULL: none reported
    quotas_at REAL,                -- when they were reported
    git INTEGER,                   -- a computer's: its program's last report said it has git (1) or not (0), so it
                                   -- can write the repository's files (w2); NULL: not said (a program before 0.1.12)
    machine TEXT,                  -- a computer's: the machine id its program sent (w3: 32 hex characters, random, made
                                   -- once in its state folder), the same in every project; NULL: not said (a program
                                   -- before 0.1.13)
    version TEXT                   -- a computer's: the version of its program, as its last report said; NULL: not said
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
    active_at REAL,                 -- the session's last activity as the program reported it (its record's
                                    -- modification time); NULL: not said
    PRIMARY KEY (credential_id, session)
);
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,     -- without the '#'
    created_by INTEGER,            -- person id; NULL for the channel the project was created with
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS channel_overrides (
    channel_id INTEGER NOT NULL,   -- a group's read or post in one channel: allow or deny (no row: inherit)
    group_id INTEGER NOT NULL,
    perm TEXT NOT NULL,            -- read, post
    value TEXT NOT NULL,           -- allow, deny
    PRIMARY KEY (channel_id, group_id, perm)
);
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
    sent REAL NOT NULL,
    notice INTEGER,                -- 1: a notice of presence (never asks for an answer); NULL: any other message
    schedule_id INTEGER,           -- the schedule that posted it; NULL: posted by hand (or by the system)
    sender_model TEXT,             -- an agent sender's model when it was sent; NULL: unknown, or not an agent
    asks_status INTEGER,           -- 1: it asks its agent for a status update (statuses.UPDATE_DUE), which the
                                   -- agent's next set_status answers; NULL: any other message
    edited REAL,                   -- when its author (a person) last edited its text (1y); NULL: never
    deleted REAL                   -- when it was deleted (1y): its text is gone for good ('') and its place kept;
                                   -- NULL: not deleted
);
CREATE INDEX IF NOT EXISTS messages_place ON messages(place, id);
CREATE TABLE IF NOT EXISTS reactions (
    message_id INTEGER NOT NULL,   -- a person's emoji reaction to a message (1y); agents do not react
    emoji TEXT NOT NULL,
    person_id INTEGER NOT NULL,
    at REAL NOT NULL,
    PRIMARY KEY (message_id, emoji, person_id)
);
CREATE INDEX IF NOT EXISTS messages_speaker ON messages(sender_kind, sender_id, place, sent);
CREATE TABLE IF NOT EXISTS levels (
    message_id INTEGER NOT NULL,   -- one row per reader, written when the message is sent
    reader_kind TEXT NOT NULL,     -- person, agent
    reader_id INTEGER NOT NULL,
    level TEXT NOT NULL,           -- important, normal, muted
    seen REAL,                     -- an agent was handed the whole message by `messages`, or no longer needs it
                                   -- (a run of a schedule superseded for it)
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
CREATE TABLE IF NOT EXISTS avatars (
    member_kind TEXT NOT NULL,     -- person, agent: a member's picture in this project (1z), set by the person (an
    member_id INTEGER NOT NULL,    -- agent's by its person)
    image BLOB NOT NULL,           -- a PNG or WebP of 128x128, at most avatars.MOST bytes
    mime TEXT NOT NULL,            -- image/png, image/webp
    version TEXT NOT NULL,         -- changes with every picture: the ETag, and what members' views say
    at REAL NOT NULL,
    PRIMARY KEY (member_kind, member_id)
);
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL,    -- its creator; the runs are posted in their name
    place TEXT NOT NULL,           -- where it posts, as messages.place
    to_name TEXT NOT NULL,         -- that place as the creator named it: '#name' or a member's name
    text TEXT NOT NULL,
    level TEXT NOT NULL,           -- important, normal, muted: the level of every reader (see messaging)
    start_at REAL NOT NULL,
    every_s INTEGER,               -- NULL: it runs once
    next_at REAL,                  -- the next run; in the past only for a time missed, made up by one run
    paused INTEGER NOT NULL DEFAULT 0,
    paused_because TEXT,           -- permission, target; NULL when paused by hand
    last_message INTEGER,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chain_reminders (
    agent_id INTEGER NOT NULL,     -- the agent was reminded once about replying to this message
    reply_to INTEGER NOT NULL,
    PRIMARY KEY (agent_id, reply_to)
);
CREATE TABLE IF NOT EXISTS replays (
    scope TEXT NOT NULL,           -- digest of the caller: a person, or a credential with its session header
    key TEXT NOT NULL,             -- the request's Idempotency-Key
    path TEXT NOT NULL,
    body TEXT NOT NULL,            -- digest of the request's body, its JSON compared after parsing (replays.py)
    status INTEGER NOT NULL,       -- the answer given, kept to be given again (below 500 only)
    answer BLOB NOT NULL,
    created REAL NOT NULL,
    PRIMARY KEY (scope, key)
);
CREATE INDEX IF NOT EXISTS replays_created ON replays(created);
CREATE TABLE IF NOT EXISTS agent_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- an agent's changes of state, for its timeline (timeline.py); kept since f6b
    agent_id INTEGER NOT NULL,
    state TEXT NOT NULL,           -- online, offline, status
    reason TEXT,                   -- offline: why (presence.OFFLINE_BECAUSE)
    title TEXT,                    -- status: the new title ('' when cleared)
    after_message INTEGER NOT NULL, -- the newest message id when it happened: the timeline puts it after that message
    at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS agent_states_agent ON agent_states(agent_id, after_message, id);
CREATE TABLE IF NOT EXISTS upgrades (
    name TEXT PRIMARY KEY,         -- a one-time change of data (ADDED_PERMISSIONS) that was made, or found not needed
    at REAL NOT NULL
);
"""


# Columns added after a table first shipped: a database made by an earlier version gets them when opened.
# The optional third item fills the new column of the rows that existed before (an SQL expression). The accounts
# database and a project's have their own lists.
ACCOUNTS_ADDED_COLUMNS = {
    "people": [("locale", "TEXT"), ("writer", "TEXT")],
}
ADDED_COLUMNS = {
    "agents": [("offline_reason", "TEXT"), ("announced", "INTEGER"), ("last_tool", "REAL"), ("quiet_since", "REAL"),
               ("model", "TEXT"), ("status_title", "TEXT NOT NULL DEFAULT ''"),
               ("status_body", "TEXT NOT NULL DEFAULT ''"), ("status_at", "REAL"), ("update_every_h", "INTEGER"),
               ("update_every_at", "REAL"), ("status_reminded", "REAL")],
    "credentials": [("via", "TEXT", "CASE kind WHEN 'connector' THEN 'connector' ELSE 'device' END"),
                    ("last_poll", "REAL"), ("connected", "INTEGER"), ("quotas", "TEXT"), ("quotas_at", "REAL"),
                    ("git", "INTEGER"), ("machine", "TEXT"), ("version", "TEXT")],
    "computer_sessions": [("active_at", "REAL")],
    # Until tasks came, every message from the system was a notice of presence.
    "messages": [("notice", "INTEGER", "CASE sender_kind WHEN 'system' THEN 1 END"), ("schedule_id", "INTEGER"),
                 ("sender_model", "TEXT"), ("asks_status", "INTEGER"), ("edited", "REAL"), ("deleted", "REAL")],
    # The groups that existed before groups had an order keep the order of their ids; default groups have none.
    "groups": [("position", "INTEGER", "CASE kind WHEN 'default' THEN NULL ELSE (SELECT count(*) FROM groups g2 "
                                       "WHERE g2.kind != 'default' AND g2.id < groups.id) END"),
               ("separate", "INTEGER NOT NULL DEFAULT 0")],
    "people": [("last_beat", "REAL"), ("status_title", "TEXT NOT NULL DEFAULT ''"), ("status_at", "REAL")],
    "agent_states": [("title", "TEXT")],
    # Until f6 the system's notices went to #general, the channel every project was created with.
    "project": [("notice_channel", "INTEGER", "(SELECT id FROM channels WHERE name = 'general')")],
}

# Indexes on such added columns: made after the columns, since the schema script runs before them.
ADDED_INDEXES = {
    "messages": ["CREATE INDEX IF NOT EXISTS messages_schedule ON messages(schedule_id) WHERE schedule_id IS NOT NULL"],
}


# Permissions a default group gained after it shipped: a database made by an earlier version gives them to that
# group, once (custom groups are never touched). Once, since f6: people set the permissions of human and ai, so a
# permission taken away must not come back at the next start. Each (group, permission) is written down in `upgrades`
# when given, or when the database has no such group yet (it is made with the permissions of today).
ADDED_PERMISSIONS = {"owner": ["manage_channels"]}

# Permissions withdrawn after they shipped: taken out of every group's list when a database is opened (a list that
# holds none of them is left as it is). The task board was withdrawn in 1s, with the permissions and the switch that
# only served it.
DROPPED_PERMISSIONS = ("assign_tasks", "edit_tasks", "coordinate_tasks", "others_assign")

# The four switches of an ownership group were columns until f6; since then they are permissions of that group, kept
# in its JSON list. A database made by an earlier version has the switches that were on moved into the list, and the
# columns dropped, when opened (others_assign then goes with the tasks, DROPPED_PERMISSIONS).
SWITCH_COLUMNS = ("others_mention", "others_channel", "others_assign", "others_regroup")


# Tables dropped after they shipped: a database made by an earlier version loses them when opened. Pins were retired
# in 1z, commands to agents on 2026-11-18, tasks in 1s (their indexes go with the tables).
DROPPED_TABLES = ("device_requests", "pins", "commands", "tasks")

# Data an earlier version allowed and this one does not, made right when a database is opened: (table, statement).
# Each statement leaves a database that is already right unchanged, so running it on every opening is safe.
DATA_FIXES = (
    # f7: the owner group takes no channel override (its people are never denied, so one had no effect but to
    # mislead); one set before is dropped.
    ("channel_overrides", "DELETE FROM channel_overrides WHERE group_id IN "
                          "(SELECT id FROM groups WHERE kind = 'default' AND name = 'owner')"),
    # Commands to agents were withdrawn on 2026-11-18: their deliveries (kind command, for the agent's program, never
    # for the agent) go, so that none is ever handed to an agent as a message. The system's replies that told their
    # outcomes stay, as written (their English text).
    ("deliveries", "DELETE FROM deliveries WHERE kind = 'command'"),
    # Tasks were withdrawn in 1s: the changes of tasks in agents' timelines go with them (they named tasks that no
    # longer exist).
    ("agent_states", "DELETE FROM agent_states WHERE state NOT IN ('online', 'offline', 'status')"),
)


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None


def _upgrade(conn: sqlite3.Connection, added_columns: dict[str, list[tuple[str, ...]]],
             dropped_columns: dict[str, tuple[tuple[str, ...], Callable[[sqlite3.Connection, list[str]], None]]]) -> None:
    for table in DROPPED_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    for table, cols in added_columns.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not have:
            continue
        for name, kind, *fill in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
                if fill:
                    conn.execute(f"UPDATE {table} SET {name} = {fill[0]}")
    for table, statements in ADDED_INDEXES.items():
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone():
            for sql in statements:
                conn.execute(sql)
    if _has_table(conn, "groups") and _has_table(conn, "upgrades"):
        for gname, perms in ADDED_PERMISSIONS.items():
            for p in perms:
                key = f"permission:{gname}:{p}"
                if conn.execute("SELECT 1 FROM upgrades WHERE name = ?", (key,)).fetchone():
                    continue
                row = conn.execute("SELECT id, permissions FROM groups WHERE kind = 'default' AND name = ?",
                                   (gname,)).fetchone()
                if row is not None and p not in json.loads(row[1]):
                    conn.execute("UPDATE groups SET permissions = ? WHERE id = ?",
                                 (json.dumps(json.loads(row[1]) + [p]), row[0]))
                conn.execute("INSERT INTO upgrades (name, at) VALUES (?, ?)", (key, util.now()))
    for table, (columns, move) in dropped_columns.items():
        if _has_table(conn, table):
            _rebuild(conn, table, columns, move)
    if _has_table(conn, "groups"):
        for gid, raw in conn.execute("SELECT id, permissions FROM groups").fetchall():
            perms = json.loads(raw)
            if set(perms) & set(DROPPED_PERMISSIONS):
                conn.execute("UPDATE groups SET permissions = ? WHERE id = ?",
                             (json.dumps([p for p in perms if p not in DROPPED_PERMISSIONS]), gid))
    for table, sql in DATA_FIXES:
        if _has_table(conn, table):
            conn.execute(sql)
    conn.commit()


def _move_switches(conn: sqlite3.Connection, moved: list[str]) -> None:
    """The switches that are on are moved into the ownership groups' permissions, unless an earlier start did that
    already (`switches_moved`)."""
    if conn.execute("SELECT 1 FROM upgrades WHERE name = 'switches_moved'").fetchone():
        return
    for r in conn.execute(f"SELECT id, permissions, {', '.join(moved)} FROM groups "
                          f"WHERE kind = 'ownership'").fetchall():
        perms = json.loads(r[1])
        perms += [c for c in moved if r[c] and c not in perms]
        conn.execute("UPDATE groups SET permissions = ? WHERE id = ?", (json.dumps(perms), r[0]))
    conn.execute("INSERT INTO upgrades (name, at) VALUES ('switches_moved', ?)", (util.now(),))


# Columns dropped after they shipped: table -> (the columns, what keeps what they held). A table that still has one of
# them is rebuilt without them (_rebuild), so this happens once.
# - groups: the four switches of an ownership group were columns until f6; since then they are permissions of that
#   group, kept in its JSON list.
# - messages, agent_states: what pointed at a task (the message asking for a task's body update; a task's change in
#   a timeline, and who made it) goes with the tasks (1s). Nothing is carried over.
# - people: the computer a person chose to write the repository's files was a credential of each project until w3;
#   since then it is a machine id kept with the account (accounts' people.writer). Nothing is carried over: the
#   account's choice starts as none (the hub had no computer chosen when w3 came), so the person is on the server
#   path until they choose again.
# Only a project's database has these tables (the accounts database has a `people` of its own: never rebuilt).
DROPPED_COLUMNS = {"groups": (SWITCH_COLUMNS, _move_switches), "people": (("writer",), lambda conn, moved: None),
                   "messages": (("task_id",), lambda conn, moved: None),
                   "agent_states": (("task_id", "by_kind", "by_id"), lambda conn, moved: None)}


def _rebuild(conn: sqlite3.Connection, table: str, columns: tuple[str, ...],
             move: Callable[[sqlite3.Connection, list[str]], None]) -> None:
    """A table that still has dropped columns: `move` keeps what they held, and the table is rebuilt without them by
    copy, as SQLite's own procedure for a change ALTER TABLE cannot make (the hub's SQLite, 3.34, has no DROP COLUMN,
    which came with 3.35): the table of today's schema is made under another name, every row copied with its id (so
    whatever points at a row still does), the old table dropped, the new one renamed, its indexes made again (those
    on its added columns too) and its AUTOINCREMENT counter kept, so that no id is ever used twice. All
    of it is one transaction, with foreign keys off (a pragma that can only change outside a transaction) and
    `foreign_key_check` empty before it commits; on any failure nothing is changed. A table without the columns is
    left alone."""
    have = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    moved = [c for c in columns if c in have]
    if not moved:
        return
    body = re.search(rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\);", PROJECT_SCHEMA, re.S).group(1)
    indexes = re.findall(rf"CREATE (?:UNIQUE )?INDEX IF NOT EXISTS \w+ ON {table}\(.*?\);", PROJECT_SCHEMA)
    indexes += ADDED_INDEXES.get(table, [])
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN IMMEDIATE")
        move(conn, moved)
        seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)).fetchone() \
            if _has_table(conn, "sqlite_sequence") else None
        have = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        conn.execute(f"DROP TABLE IF EXISTS {table}_rebuilt")
        conn.execute(f"CREATE TABLE {table}_rebuilt ({body}\n)")
        keep = ", ".join(r[1] for r in conn.execute(f"PRAGMA table_info({table}_rebuilt)") if r[1] in have)
        conn.execute(f"INSERT INTO {table}_rebuilt ({keep}) SELECT {keep} FROM {table}")
        conn.execute(f"DROP TABLE {table}")
        conn.execute(f"ALTER TABLE {table}_rebuilt RENAME TO {table}")
        if seq is not None:
            conn.execute("UPDATE sqlite_sequence SET seq = max(seq, ?) WHERE name = ?", (seq[0], table))
        for sql in indexes:
            conn.execute(sql)
        broken = conn.execute("PRAGMA foreign_key_check").fetchall()
        if broken:
            raise sqlite3.IntegrityError(f"foreign keys broken by rebuilding {table}: {broken[:5]}")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _open(path: Path, schema: str, added_columns: dict[str, list[tuple[str, ...]]],
          dropped_columns: dict[str, Any]) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema)
    _upgrade(conn, added_columns, dropped_columns)
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
            self._accounts = _open(self.data / "accounts.db", ACCOUNTS_SCHEMA, ACCOUNTS_ADDED_COLUMNS, {})
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
            conn = self._projects[slug] = _open(path, PROJECT_SCHEMA, ADDED_COLUMNS, DROPPED_COLUMNS)
        return conn

    def slugs(self) -> list[str]:
        return sorted(p.stem for p in self.projects_dir.glob("*.db") if util.valid_slug(p.stem))

    def new_project_db(self, slug: str) -> tuple[sqlite3.Connection, Path]:
        tmp = self.projects_dir / f".{slug}.db.part"
        if tmp.exists():
            tmp.unlink()
        return _open(tmp, PROJECT_SCHEMA, ADDED_COLUMNS, DROPPED_COLUMNS), tmp

    def publish_project_db(self, conn: sqlite3.Connection, tmp: Path, slug: str) -> None:
        conn.commit()
        conn.close()
        os.replace(tmp, self.project_path(slug))

    def drop_project(self, slug: str) -> None:
        """Delete a project's database for good: its connection is closed and its file, with SQLite's side files,
        removed. The project does not exist from then on."""
        conn = self._projects.pop(slug, None)
        if conn is not None:
            conn.close()
        path = self.project_path(slug)
        for p in [path] + [path.with_name(path.name + x) for x in ("-wal", "-shm", "-journal")]:
            if p.exists():
                p.unlink()

    def close(self) -> None:
        for c in [self._accounts, *self._projects.values()]:
            if c is not None:
                c.close()
        self._accounts, self._projects = None, {}
