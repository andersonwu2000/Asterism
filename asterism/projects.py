"""A project's own data: members, groups and permissions, invitations, credentials.

Every entrance (web JSON API, pages, the agent API, MCP tools) calls these functions; none of them
repeats a rule. A function that needs a permission takes an Actor and checks it here.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable

from . import accounts, config, downloads, presence, util
from .errors import bad_request, conflict, forbidden, gone, not_found
from .store import Store

PERMISSIONS = ["read", "post", "create_channel", "create_schedule", "manage_own_agents", "manage_members",
               "manage_groups", "manage_channels", "project_settings"]
MANAGEMENT = {"manage_members", "manage_groups", "manage_channels", "project_settings"}
DEFAULT_GROUPS = [
    ("owner", PERMISSIONS),
    ("human", ["read", "post", "create_channel", "create_schedule", "manage_own_agents"]),
    ("ai", ["read", "post"]),
]
# The permissions only a person's own agent group (ownership) carries, set only by that person: what others may do
# with that person's agents (until f6 they were called its switches, and the API still sets them that way too). Since
# 1e an agent is reached from its own side only: the switches that let others mention it or let it hear their channel
# talk are withdrawn; what remains is that others may change the groups of these agents.
SWITCHES = ("others_regroup",)
OWNERSHIP_SUFFIX = "-agents"
NAME_RULE = "A name is 1 to 40 letters, digits, '.', '_' or '-', starting with a letter or digit."
GROUP_NAME_RULE = ("A group's name is 1 to 40 letters or digits of any script, '.', '_' or '-', starting with a letter or "
                   "digit: no spaces, '@', '#', '/' or quotes.")
# What a channel may override per group, and how (no row: inherit).
CHANNEL_PERMISSIONS = ("read", "post")
OVERRIDES = ("allow", "deny", "inherit")
PROJECT_REPO_RE = re.compile(r"https://github\.com/[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}")


@dataclass(frozen=True)
class Actor:
    """Who is acting: a person, or an agent (then person_id is the agent's person)."""
    person_id: int
    agent_id: int | None = None


@dataclass
class Project:
    store: Store
    slug: str
    db: sqlite3.Connection

    @property
    def accounts(self) -> sqlite3.Connection:
        return self.store.accounts()

    def row(self) -> sqlite3.Row:
        return self.db.execute("SELECT * FROM project WHERE id = 1").fetchone()


def open_project(store: Store, slug: str) -> Project:
    db = store.project(slug)
    if db is None:
        raise not_found(f"There is no project '{slug}'.")
    return Project(store, slug, db)


def notice_channel(pj: Project) -> str:
    """The channel (its name, without '#') the system's notices go to: the one the project chose, else its first
    channel. A project always keeps at least one channel (the notice channel cannot be deleted)."""
    r = pj.db.execute("SELECT c.name FROM project p JOIN channels c ON c.id = p.notice_channel WHERE p.id = 1").fetchone()
    if r is None:
        r = pj.db.execute("SELECT name FROM channels ORDER BY id LIMIT 1").fetchone()
    return r["name"] if r else ""


def info(pj: Project) -> dict[str, str]:
    r = pj.row()
    return {"name": r["name"], "slug": r["slug"], "repo": r["repo"]}


# --------------------------------------------------------------------------- creating a project (admin)

def create_project(store: Store, slug: str, name: str, repo: str, owner_login: str) -> None:
    """A new project's database: the default groups and one channel, #general, where the notices go. The account
    with the GitHub login `owner_login` becomes its owner the first time it turns up (member)."""
    if not util.valid_slug(slug):
        raise ValueError("the slug must match [a-z0-9][a-z0-9-]{0,39} and not be a reserved word")
    if not name.strip():
        raise ValueError("the name must not be empty")
    if not util.GITHUB_LOGIN_RE.fullmatch(owner_login):
        raise ValueError("the owner must be a GitHub login")
    if repo and not repo.startswith(("https://", "http://")):
        raise ValueError("the repo must be an address (https://...)")
    if store.project(slug) is not None:
        raise ValueError(f"the project '{slug}' exists already")
    conn, tmp = store.new_project_db(slug)
    t = util.now()
    cid = conn.execute("INSERT INTO channels (name, created) VALUES ('general', ?)", (t,)).lastrowid
    conn.execute("INSERT INTO project (id, slug, name, repo, owner_login, created, notice_channel) "
                 "VALUES (1, ?, ?, ?, ?, ?, ?)", (slug, name.strip(), repo, owner_login, t, cid))
    for gname, perms in DEFAULT_GROUPS:
        conn.execute("INSERT INTO groups (name, kind, permissions, created) VALUES (?, 'default', ?, ?)",
                     (gname, json.dumps(perms), t))
    store.publish_project_db(conn, tmp, slug)


PROJECT_NAME_MAX = 80
REPO_RULE = "The repository is an address https://github.com/{owner}/{name}, or empty for none."


def _project_name(v: Any) -> str:
    if not isinstance(v, str) or not v.strip() or len(v.strip()) > PROJECT_NAME_MAX:
        raise bad_request("invalid_name", f"The project's name is 1 to {PROJECT_NAME_MAX} characters.")
    return v.strip()


def _repo(v: Any) -> str:
    if v is None or v == "":
        return ""
    if not isinstance(v, str) or not PROJECT_REPO_RE.fullmatch(v.strip().removesuffix(".git").rstrip("/")):
        raise bad_request("invalid_repo", REPO_RULE)
    return v.strip().removesuffix(".git").rstrip("/")


def new_project(store: Store, person: sqlite3.Row, body: dict[str, Any]) -> dict[str, Any]:
    """Anyone signed in makes a project (it lives on this server); they are its owner, in owner and human. The server
    chooses its address (1y): random, never a reserved word nor one in use (a `slug` sent is ignored); names may
    repeat."""
    name, repo = _project_name(body.get("name")), _repo(body.get("repo"))
    slug = util.new_slug()
    while not util.valid_slug(slug) or store.project(slug) is not None or store.project_path(slug).exists():
        slug = util.new_slug()
    create_project(store, slug, name, repo, person["github_login"])
    pj = open_project(store, slug)
    member(pj, person)                 # the creator turns up at once and becomes the owner
    util.log("project_created", project=slug, by=person["id"])
    return {"project": info(pj), "slug": slug}


def change_project(pj: Project, actor: Actor, body: dict[str, Any]) -> dict[str, Any]:
    """Rename the project, set or change its repository, choose the channel the notices go to (project_settings)."""
    _person_only(actor)
    require(pj, actor, "project_settings", "Changing the project needs the project_settings permission.")
    if not {"name", "repo", "notice_channel"} & set(body):
        raise bad_request("bad_request", "Say what to change: name, repo or notice_channel.")
    cols: dict[str, Any] = {}
    if "name" in body:
        cols["name"] = _project_name(body["name"])
    if "repo" in body:
        cols["repo"] = _repo(body["repo"])
    if "notice_channel" in body:
        where = body["notice_channel"]
        name = where[1:] if isinstance(where, str) and where.startswith("#") else where
        c = pj.db.execute("SELECT id FROM channels WHERE name = ?", (name,)).fetchone() if isinstance(name, str) else None
        if c is None:
            raise not_found(f"There is no channel '{where}'.")
        cols["notice_channel"] = c["id"]
    sets = ", ".join(f"{k} = ?" for k in cols)          # keys are this function's own column names
    with pj.db:
        pj.db.execute(f"UPDATE project SET {sets} WHERE id = 1", tuple(cols.values()))
    util.log("project_changed", project=pj.slug, what=sorted(cols), by=actor.person_id)
    return {"project": dict(info(pj), notice_channel="#" + notice_channel(pj))}


def delete_project(pj: Project, actor: Actor, confirm: Any) -> None:
    """Delete the project and everything in it, at once and for good. Its credentials stop working (their polls are
    ended first; afterwards a credential for it is refused as a revoked one) and so do its connectors' tokens. The
    caller removes the database (Store.drop_project) once the ended polls have let go of it."""
    _person_only(actor)
    require(pj, actor, "project_settings", "Deleting the project needs the project_settings permission.")
    name = pj.row()["name"]
    if confirm != name:
        raise bad_request("bad_request", f"To delete the project, send confirm with its name, '{name}'.")
    _revoke(pj, "1 = 1", ())
    with pj.accounts:
        pj.accounts.execute("DELETE FROM oauth_tokens WHERE slug = ?", (pj.slug,))
        pj.accounts.execute("DELETE FROM oauth_codes WHERE slug = ?", (pj.slug,))
    util.log("project_deleted", project=pj.slug, by=actor.person_id)


# --------------------------------------------------------------------------- names

def check_name(name: Any) -> str:
    if not util.valid_name(name):
        raise bad_request("invalid_name", NAME_RULE)
    return name


def check_group_name(name: Any) -> str:
    """A custom group's name may be written in any script (1y); people's and agents' names keep NAME_RULE."""
    if not util.valid_group_name(name):
        raise bad_request("invalid_name", GROUP_NAME_RULE)
    return name


def name_holder(pj: Project, name: str) -> tuple[str, sqlite3.Row] | None:
    """What holds a name in this project, ignoring case: people, agents and groups can all be @-mentioned."""
    for kind, sql in (("person", "SELECT * FROM people WHERE lower(name) = lower(?)"),
                      ("agent", "SELECT * FROM agents WHERE lower(name) = lower(?)"),
                      ("group", "SELECT * FROM groups WHERE lower(name) = lower(?)")):
        row = pj.db.execute(sql, (name,)).fetchone()
        if row:
            return kind, row
    return None


def describe_holder(pj: Project, holder: tuple[str, sqlite3.Row]) -> str:
    kind, row = holder
    if kind == "agent":
        return f"'{row['name']}' is an agent of {person_name(pj, row['person_id'])}"
    if kind == "person":
        return f"'{row['name']}' is a person in this project"
    return f"'{row['name']}' is a group in this project"


def set_name(pj: Project, actor: Actor, new: Any) -> dict[str, Any]:
    """A person's name in this project (their GitHub login does not change): the name rules, and no other person,
    agent or group of the project holds it. Everything that shows the person uses it from then on, the senders of
    their past messages included; their own agent group follows it ('<name>-agents'). Mentions written with the old
    name stay as they were written."""
    _person_only(actor)
    check_name(new)
    if new.lower().endswith(OWNERSHIP_SUFFIX):
        raise conflict(f"Names ending in '{OWNERSHIP_SUFFIX}' are kept for each person's own group. Choose another name.")
    me = pj.db.execute("SELECT * FROM people WHERE person_id = ?", (actor.person_id,)).fetchone()
    own = ownership_group(pj, actor.person_id)
    for n, mine in ((new, ("person", actor.person_id)), (new + OWNERSHIP_SUFFIX, ("group", own["id"] if own else None))):
        holder = name_holder(pj, n)
        if holder and (holder[0], holder[1]["person_id" if holder[0] == "person" else "id"]) != mine:
            raise conflict(describe_holder(pj, holder) + ". Choose another name.")
    old = me["name"]
    with pj.db:
        pj.db.execute("UPDATE people SET name = ? WHERE person_id = ?", (new, actor.person_id))
        pj.db.execute("UPDATE messages SET sender_name = ? WHERE sender_kind = 'person' AND sender_id = ?",
                      (new, actor.person_id))
        pj.db.execute("UPDATE schedules SET to_name = ? WHERE to_name = ? AND place LIKE 'p:%' AND "
                      "instr('|' || substr(place, 3) || '|', ?) > 0", (new, old, f"|person:{actor.person_id}|"))
        if own:
            pj.db.execute("UPDATE groups SET name = ? WHERE id = ?", (new + OWNERSHIP_SUFFIX, own["id"]))
    util.log("person_renamed", project=pj.slug, person=actor.person_id)
    return {"name": new}


def person_name(pj: Project, person_id: int) -> str:
    r = pj.db.execute("SELECT name FROM people WHERE person_id = ?", (person_id,)).fetchone()
    return r["name"] if r else "a former member"


# --------------------------------------------------------------------------- groups and permissions

def group_by_name(pj: Project, name: str) -> sqlite3.Row | None:
    return pj.db.execute("SELECT * FROM groups WHERE name = ?", (name,)).fetchone()


def ownership_group(pj: Project, person_id: int) -> sqlite3.Row:
    return pj.db.execute("SELECT * FROM groups WHERE kind = 'ownership' AND owner_person = ?", (person_id,)).fetchone()


def groups_of(pj: Project, kind: str, member_id: int) -> list[sqlite3.Row]:
    return pj.db.execute("SELECT g.* FROM groups g JOIN group_members m ON m.group_id = g.id "
                         "WHERE m.member_kind = ? AND m.member_id = ? ORDER BY g.id", (kind, member_id)).fetchall()


def _is_owner_group(g: sqlite3.Row) -> bool:
    return g["kind"] == "default" and g["name"] == "owner"


def _perms(rows: Iterable[sqlite3.Row]) -> set[str]:
    """The union of the groups' permissions; `owner` always holds every permission, whatever its row says."""
    out: set[str] = set()
    for g in rows:
        out.update(PERMISSIONS if _is_owner_group(g) else json.loads(g["permissions"]))
    return out


def person_permissions(pj: Project, person_id: int) -> set[str]:
    """The union over the person's groups."""
    return _perms(groups_of(pj, "person", person_id))


def agent_permissions(pj: Project, agent: sqlite3.Row) -> set[str]:
    """What its groups give, capped by its person, and never management, whatever the groups say."""
    return (_perms(groups_of(pj, "agent", agent["id"])) & person_permissions(pj, agent["person_id"])) - MANAGEMENT


def permissions(pj: Project, actor: Actor) -> set[str]:
    if actor.agent_id is None:
        return person_permissions(pj, actor.person_id)
    a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (actor.agent_id,)).fetchone()
    return agent_permissions(pj, a) if a else set()


def require(pj: Project, actor: Actor, perm: str, message: str) -> None:
    if perm not in permissions(pj, actor):
        raise forbidden(message)


# --------------------------------------------------------------------------- channel permissions

def _overrides(pj: Project) -> dict[str, dict[int, dict[str, str]]]:
    """channel name -> group id -> permission -> allow | deny (what is not there inherits)."""
    out: dict[str, dict[int, dict[str, str]]] = {}
    for r in pj.db.execute("SELECT c.name, o.group_id, o.perm, o.value FROM channel_overrides o "
                           "JOIN channels c ON c.id = o.channel_id"):
        out.setdefault(r["name"], {}).setdefault(r["group_id"], {})[r["perm"]] = r["value"]
    return out


def channel_access(pj: Project, kind: str, member_id: int) -> dict[str, set[str]]:
    """channel name -> what of read and post a member (person or agent) holds there, as Discord's channel overrides:
    from the member's project permissions, an override that allows one to any of the member's groups grants it there,
    even one the member lacks in the project; one that denies it to any of them takes it away, unless another allows
    it (allow wins over deny among the groups). People in `owner` are never denied. An agent never holds in a channel
    what its person does not hold there."""
    names = [r["name"] for r in pj.db.execute("SELECT name FROM channels ORDER BY id")]
    if kind == "person":
        groups = groups_of(pj, "person", member_id)
        base = person_permissions(pj, member_id) & set(CHANNEL_PERMISSIONS)
        exempt, cap = any(_is_owner_group(g) for g in groups), None
    else:
        a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (member_id,)).fetchone()
        if a is None:
            return {n: set() for n in names}
        groups = groups_of(pj, "agent", member_id)
        base = agent_permissions(pj, a) & set(CHANNEL_PERMISSIONS)
        exempt, cap = False, channel_access(pj, "person", a["person_id"])
    over = _overrides(pj)
    out: dict[str, set[str]] = {}
    for n in names:
        have = set(base)
        o = over.get(n, {})
        if o:
            for p in CHANNEL_PERMISSIONS:
                said = {o.get(g["id"], {}).get(p) for g in groups}
                if "allow" in said:
                    have.add(p)
                elif "deny" in said and not exempt:
                    have.discard(p)
        if cap is not None:
            have &= cap.get(n, set())
        out[n] = have
    return out


def readable_channels(pj: Project, kind: str, member_id: int) -> list[str]:
    """The channels (names, in their order) a member may read; any other does not exist for that member."""
    return [n for n, have in channel_access(pj, kind, member_id).items() if "read" in have]


def channel_readers(pj: Project, name: str) -> dict[str, list[str]]:
    """Who may read a channel now: the people (in the order they joined) and the agents (by id), by name."""
    people = [r["name"] for r in pj.db.execute("SELECT person_id, name FROM people ORDER BY joined, person_id")
              if "read" in channel_access(pj, "person", r["person_id"]).get(name, set())]
    agents = [r["name"] for r in pj.db.execute("SELECT id, name FROM agents ORDER BY id")
              if "read" in channel_access(pj, "agent", r["id"]).get(name, set())]
    return {"people": people, "agents": agents}


def restricted_channels(pj: Project) -> set[str]:
    """The channels a member of the project may not read because of the channel's own overrides (a channel without
    any is read as the project's permissions say, the same for every channel)."""
    over = {r["name"] for r in pj.db.execute("SELECT DISTINCT c.name FROM channel_overrides o "
                                             "JOIN channels c ON c.id = o.channel_id")}
    if not over:
        return set()
    out: set[str] = set()
    members = [("person", r[0]) for r in pj.db.execute("SELECT person_id FROM people")] + \
              [("agent", r[0]) for r in pj.db.execute("SELECT id FROM agents")]
    for kind, mid in members:
        have = channel_access(pj, kind, mid)
        out |= {n for n in over if "read" not in have.get(n, set())}
        if out == over:
            break
    return out


def channel_overrides(pj: Project, channel_id: int) -> dict[str, dict[str, str]]:
    """Every group, in the groups' order, with its read and post in the channel: allow, deny or inherit."""
    rows = {(r["group_id"], r["perm"]): r["value"] for r in pj.db.execute(
        "SELECT group_id, perm, value FROM channel_overrides WHERE channel_id = ?", (channel_id,))}
    return {g["name"]: {p: rows.get((g["id"], p), "inherit") for p in CHANNEL_PERMISSIONS} for g in ordered_groups(pj)}


def set_channel_overrides(pj: Project, actor: Actor, channel_id: int, body: Any) -> dict[str, dict[str, str]]:
    """Set what the groups named in `body` ({group: {"read"|"post": "allow"|"deny"|"inherit"}}) hold in a channel;
    what is not named stays as it is (manage_channels). Refused if afterwards nobody could read the channel."""
    _person_only(actor)
    require(pj, actor, "manage_channels", "Changing a channel's permissions needs the manage_channels permission.")
    if not isinstance(body, dict) or not all(isinstance(v, dict) for v in body.values()):
        raise bad_request("bad_request", 'overrides is {"<group>": {"read": "allow" | "deny" | "inherit", "post": ...}}.')
    writes = []
    for gname, perms in body.items():
        g = group_by_name(pj, gname)
        if g is None:
            raise not_found(f"There is no group '{gname}'.")
        for p, v in perms.items():
            if p not in CHANNEL_PERMISSIONS or v not in OVERRIDES:
                raise bad_request("bad_request", "A channel overrides read and post, each allow, deny or inherit.")
            if _is_owner_group(g) and v != "inherit":
                raise bad_request("bad_request", "The owner group always reads and posts in every channel; it takes "
                                                 "no override.")
            writes.append((g["id"], p, v))
    name = pj.db.execute("SELECT name FROM channels WHERE id = ?", (channel_id,)).fetchone()["name"]
    pj.db.execute("BEGIN")
    try:
        for gid, p, v in writes:
            if v == "inherit":
                pj.db.execute("DELETE FROM channel_overrides WHERE channel_id = ? AND group_id = ? AND perm = ?",
                              (channel_id, gid, p))
            else:
                pj.db.execute("INSERT OR REPLACE INTO channel_overrides (channel_id, group_id, perm, value) "
                              "VALUES (?, ?, ?, ?)", (channel_id, gid, p, v))
        people = [r["person_id"] for r in pj.db.execute("SELECT person_id FROM people")]
        if not any("read" in channel_access(pj, "person", pid).get(name, set()) for pid in people):
            raise conflict(f"Then nobody could read #{name}. Leave at least one group able to read it.")
    except BaseException:
        pj.db.rollback()
        raise
    pj.db.commit()
    util.log("channel_permissions_set", project=pj.slug, channel=name, by=actor.person_id)
    from . import presence             # presence builds on this module
    presence.kick()                    # deliveries of a channel no longer readable are dropped on the way out
    return channel_overrides(pj, channel_id)


def _person_only(actor: Actor) -> None:
    if actor.agent_id is not None:
        raise forbidden("Agents cannot manage members or groups.")


def _add_to_group(pj: Project, group_id: int, kind: str, member_id: int) -> None:
    pj.db.execute("INSERT OR IGNORE INTO group_members (group_id, member_kind, member_id) VALUES (?, ?, ?)",
                  (group_id, kind, member_id))


def _owners_left(pj: Project, without_person: int) -> int:
    g = group_by_name(pj, "owner")
    return pj.db.execute("SELECT count(*) FROM group_members WHERE group_id = ? AND member_kind = 'person' "
                         "AND member_id != ?", (g["id"], without_person)).fetchone()[0]


def _no_escalation(groups: Iterable[sqlite3.Row], mine: set[str]) -> None:
    for g in groups:
        if not set(json.loads(g["permissions"])) <= mine:
            raise forbidden(f"'{g['name']}' carries permissions you do not hold, so you cannot hand it out or take it away.")


def create_group(pj: Project, actor: Actor, name: Any, perms: Any) -> dict[str, Any]:
    _person_only(actor)
    require(pj, actor, "manage_groups", "Creating groups needs the manage_groups permission.")
    check_group_name(name)
    if name.lower().endswith(OWNERSHIP_SUFFIX):
        raise conflict(f"Names ending in '{OWNERSHIP_SUFFIX}' are kept for each person's own group. Choose another name.")
    perms = _check_permissions(perms)
    if not set(perms) <= permissions(pj, actor):
        raise forbidden("A group can only carry permissions you hold yourself.")
    holder = name_holder(pj, name)
    if holder:
        raise conflict(describe_holder(pj, holder) + ". Choose another name.")
    with pj.db:
        pj.db.execute("INSERT INTO groups (name, kind, permissions, created, position) VALUES (?, 'custom', ?, ?, ?)",
                      (name, json.dumps(perms), util.now(), _next_position(pj)))
    util.log("group_created", project=pj.slug, group=name, by=actor.person_id)
    return {"name": name, "kind": "custom", "permissions": perms}


def _check_permissions(perms: Any, own: bool = False) -> list[str]:
    """A list of permission names from the catalogue, returned in the catalogue's order; with `own` (a person's own
    agent group) also what others may do with that person's agents (SWITCHES), which no other group carries."""
    allowed = PERMISSIONS + list(SWITCHES) if own else PERMISSIONS
    if not isinstance(perms, list) or not all(isinstance(p, str) and p in allowed for p in perms):
        why = "" if own else (" (" + ", ".join(SWITCHES) + " are carried only by a person's own agent group)")
        raise bad_request("invalid_permissions", "permissions must be a list drawn from: " + ", ".join(PERMISSIONS) + why)
    return [p for p in allowed if p in perms]


def _custom_group(pj: Project, actor: Actor, name: str, need: str) -> sqlite3.Row:
    """The custom group `name`, for a person with manage_groups; default and ownership groups keep their names and
    stay."""
    _person_only(actor)
    require(pj, actor, "manage_groups", need)
    g = group_by_name(pj, name)
    if not g:
        raise not_found(f"There is no group '{name}'.")
    if g["kind"] == "default":
        raise conflict(f"'{name}' is one of the project's default groups; it keeps its name and stays.")
    if g["kind"] == "ownership":
        raise conflict(f"'{name}' holds the agents of one person and follows ownership; it keeps its name and stays.")
    return g


def _next_position(pj: Project) -> int:
    """Where a new group goes: below every other non-default group."""
    return pj.db.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM groups WHERE kind != 'default'").fetchone()[0]


def order_groups(pj: Project, actor: Actor, names: Any) -> dict[str, Any]:
    """Put the non-default groups in a new order (the first is the highest). `names` names every one of them once
    and nothing else; otherwise nothing changes."""
    _person_only(actor)
    require(pj, actor, "manage_groups", "Ordering groups needs the manage_groups permission.")
    have = [r["name"] for r in pj.db.execute("SELECT name FROM groups WHERE kind != 'default' ORDER BY position, id")]
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names)             or len(names) != len(have) or set(names) != set(have):
        raise bad_request("invalid_order", "names must list every group except the default ones (owner, human, ai), "
                                           "each once, in the new order: " + ", ".join(have) + ".")
    with pj.db:
        for i, n in enumerate(names):
            pj.db.execute("UPDATE groups SET position = ? WHERE name = ?", (i, n))
    util.log("groups_ordered", project=pj.slug, by=actor.person_id)
    return {"groups": names}


def change_group_settings(pj: Project, actor: Actor, name: str, body: dict[str, Any]) -> dict[str, Any]:
    """Change a group: its name (custom groups, rename_group), its permissions (change_group), whether it is shown
    separately in the member list, or several of these. Showing separately: a custom group for who may manage groups;
    a person's own agent group for that person or who may manage groups; never a default group."""
    if not {"name", "permissions", "separate"} & set(body):
        raise bad_request("invalid_request", "Say what to change: name, permissions or separate.")
    out: dict[str, Any] = {}
    if "separate" in body:
        separate = body["separate"]
        if not isinstance(separate, bool):
            raise bad_request("invalid_request", "separate must be true or false.")
        _person_only(actor)
        g = group_by_name(pj, name)
        if not g:
            raise not_found(f"There is no group '{name}'.")
        if g["kind"] == "default":
            raise conflict(f"'{name}' is one of the project's default groups; it is never shown as a group of its own.")
        if g["kind"] == "custom" or g["owner_person"] != actor.person_id:
            require(pj, actor, "manage_groups", "Changing groups needs the manage_groups permission.")
    if "permissions" in body:
        out = change_group(pj, actor, name, body["permissions"])
    if "separate" in body:
        with pj.db:
            pj.db.execute("UPDATE groups SET separate = ? WHERE name = ?", (int(body["separate"]), name))
        util.log("group_changed", project=pj.slug, group=name, separate=body["separate"], by=actor.person_id)
        out["separate"] = body["separate"]
    if "name" in body:
        out.update(rename_group(pj, actor, name, body["name"]))
    g = group_by_name(pj, out.get("name", name))
    return {"name": g["name"], "kind": g["kind"], "permissions": _stored(g), **out}


def _stored(g: sqlite3.Row) -> list[str]:
    """A group's permissions as shown: owner's are every permission, whatever its row says."""
    return list(PERMISSIONS) if _is_owner_group(g) else json.loads(g["permissions"])


def change_group(pj: Project, actor: Actor, name: str, perms: Any) -> dict[str, Any]:
    """Set the permissions of a group. Takes effect at once: permissions are read from the groups on every request.
    - a custom group, `human` and `ai` (as Discord's @everyone): manage_groups, and nobody gives or takes away a
      permission they do not hold themselves;
    - `owner` always holds every permission and is not changed;
    - a person's own agent group: only that person sets it; besides the ordinary permissions (its agents still never
      hold more than their person) it alone carries what others may do with that person's agents (SWITCHES)."""
    _person_only(actor)
    g = group_by_name(pj, name)
    if not g:
        raise not_found(f"There is no group '{name}'.")
    if g["kind"] == "ownership":
        if g["owner_person"] != actor.person_id:
            raise forbidden(f"'{name}' holds the agents of {person_name(pj, g['owner_person'])}; only they set what others "
                            f"may do with their agents.")
        perms = _check_permissions(perms, own=True)
    else:
        require(pj, actor, "manage_groups", "Changing groups needs the manage_groups permission.")
        if _is_owner_group(g):
            raise conflict(f"'{name}' always holds every permission; it is not changed.")
        perms = _check_permissions(perms)
    touched, mine = set(json.loads(g["permissions"])) | set(perms), permissions(pj, actor) | set(SWITCHES)
    missing = [p for p in PERMISSIONS if p in touched and p not in mine]
    if missing:
        raise forbidden(f"'{name}' carries or would carry permissions you do not hold ({', '.join(missing)}), "
                        f"so you cannot change it.")
    with pj.db:
        pj.db.execute("UPDATE groups SET permissions = ? WHERE id = ?", (json.dumps(perms), g["id"]))
    util.log("group_changed", project=pj.slug, group=name, permissions=perms, by=actor.person_id)
    return {"name": name, "kind": g["kind"], "permissions": perms}


def rename_group(pj: Project, actor: Actor, name: str, new: Any) -> dict[str, Any]:
    """A custom group gets a new name (the rules of a new group's name); default and agent groups keep theirs. Old
    messages that mentioned the old name stay as they were written."""
    g = _custom_group(pj, actor, name, "Renaming groups needs the manage_groups permission.")
    check_group_name(new)
    if new.lower().endswith(OWNERSHIP_SUFFIX):
        raise conflict(f"Names ending in '{OWNERSHIP_SUFFIX}' are kept for each person's own group. Choose another name.")
    holder = name_holder(pj, new)
    if holder and not (holder[0] == "group" and holder[1]["id"] == g["id"]):
        raise conflict(describe_holder(pj, holder) + ". Choose another name.")
    with pj.db:
        pj.db.execute("UPDATE groups SET name = ? WHERE id = ?", (new, g["id"]))
    util.log("group_renamed", project=pj.slug, group=new, was=name, by=actor.person_id)
    return {"name": new}


def remove_group(pj: Project, actor: Actor, name: str) -> dict[str, Any]:
    """Remove a custom group. Its members are simply no longer in it; its name is free again."""
    g = _custom_group(pj, actor, name, "Removing groups needs the manage_groups permission.")
    mine = permissions(pj, actor)
    missing = [p for p in json.loads(g["permissions"]) if p not in mine]
    if missing:
        raise forbidden(f"'{name}' carries permissions you do not hold ({', '.join(missing)}), so you cannot remove it.")
    with pj.db:
        pj.db.execute("DELETE FROM group_members WHERE group_id = ?", (g["id"],))
        pj.db.execute("DELETE FROM channel_overrides WHERE group_id = ?", (g["id"],))
        pj.db.execute("DELETE FROM groups WHERE id = ?", (g["id"],))
    util.log("group_removed", project=pj.slug, group=name, by=actor.person_id)
    return {"removed": name}


def change_groups(pj: Project, actor: Actor, target: str, add: Any, remove: Any) -> dict[str, Any]:
    """Put a member into groups or take it out.

    - A person changes the groups of their own agents, but adds only groups they are in themselves.
    - Anyone else needs manage_groups and, for an agent, its person's "others may change groups" switch;
      they can only add or remove groups whose permissions they hold (nobody hands out more than they have).
    - Ownership groups follow who owns an agent and are never edited here.
    - The project always keeps at least one person in `owner`.
    """
    _person_only(actor)
    add = [] if add is None else add
    remove = [] if remove is None else remove
    if not isinstance(add, list) or not isinstance(remove, list) or not all(isinstance(g, str) for g in add + remove):
        raise bad_request("invalid_request", "add and remove must be lists of group names.")
    groups = {}
    for gname in add + remove:
        g = group_by_name(pj, gname)
        if not g:
            raise not_found(f"There is no group '{gname}'.")
        if g["kind"] == "ownership":
            raise conflict(f"'{gname}' holds the agents of one person and follows ownership; it cannot be edited.")
        if g["kind"] == "default":
            raise conflict(f"'{gname}' is one of the project's default groups: who is in it follows joining, never a "
                           f"hand. Limit or widen what its members hold through its permissions or a group of your own.")
        groups[gname] = g
    mine = permissions(pj, actor)
    agent = pj.db.execute("SELECT * FROM agents WHERE name = ?", (target,)).fetchone()
    person = None if agent else pj.db.execute("SELECT * FROM people WHERE name = ?", (target,)).fetchone()
    if agent:
        kind, mid = "agent", agent["id"]
        if agent["person_id"] == actor.person_id:
            held = {g["name"] for g in groups_of(pj, "person", actor.person_id)}
            for gname in add:
                if gname not in held:
                    raise forbidden(f"You can give your agent only groups you are in yourself; you are not in '{gname}'.")
        else:
            require(pj, actor, "manage_groups", "Changing another person's agent needs the manage_groups permission.")
            if not switch_on(pj, agent["person_id"], "others_regroup"):
                raise forbidden(f"{person_name(pj, agent['person_id'])} has not allowed others to change the groups of their agents.")
            _no_escalation(groups.values(), mine)
    elif person:
        kind, mid = "person", person["person_id"]
        require(pj, actor, "manage_groups", "Changing a person's groups needs the manage_groups permission.")
        _no_escalation(groups.values(), mine)
        if "owner" in remove and "owner" not in add and _owners_left(pj, mid) == 0:
            raise conflict("The project needs at least one person in 'owner'.")
    else:
        raise not_found(f"There is no member '{target}'.")
    with pj.db:
        for gname in add:
            _add_to_group(pj, groups[gname]["id"], kind, mid)
        for gname in remove:
            if gname not in add:
                pj.db.execute("DELETE FROM group_members WHERE group_id = ? AND member_kind = ? AND member_id = ?",
                              (groups[gname]["id"], kind, mid))
    util.log("groups_changed", project=pj.slug, member=target, add=add, remove=remove, by=actor.person_id)
    return {"groups": [g["name"] for g in groups_of(pj, kind, mid)]}


# --------------------------------------------------------------------------- membership

def member(pj: Project, person: sqlite3.Row) -> sqlite3.Row | None:
    """The person's membership row. The GitHub login the project was created for becomes its owner the
    first time that account turns up."""
    row = pj.db.execute("SELECT * FROM people WHERE person_id = ?", (person["id"],)).fetchone()
    if row:
        return row
    p = pj.row()
    if p["owner_person"] is None and p["owner_login"].lower() == person["github_login"].lower():
        _admit(pj, person, ["owner", "human"])
        with pj.db:
            pj.db.execute("UPDATE project SET owner_person = ? WHERE id = 1", (person["id"],))
        util.log("owner_claimed", project=pj.slug, person=person["id"])
        return pj.db.execute("SELECT * FROM people WHERE person_id = ?", (person["id"],)).fetchone()
    return None


def require_member(pj: Project, person: sqlite3.Row) -> Actor:
    if not member(pj, person):
        raise forbidden("You are not a member of this project. Ask a member for an invitation.")
    return Actor(person["id"])


def _admit(pj: Project, person: sqlite3.Row, group_names: list[str]) -> None:
    name = person["name"]
    for n in (name, name + OWNERSHIP_SUFFIX):
        holder = name_holder(pj, n)
        if holder:
            raise conflict(f"Cannot join: {describe_holder(pj, holder)}. Ask the project's managers to rename it.")
    t = util.now()
    with pj.db:
        pj.db.execute("INSERT INTO people (person_id, name, joined) VALUES (?, ?, ?)", (person["id"], name, t))
        for gname in group_names:
            _add_to_group(pj, group_by_name(pj, gname)["id"], "person", person["id"])
        pj.db.execute("INSERT INTO groups (name, kind, permissions, owner_person, created, position) "
                      "VALUES (?, 'ownership', '[]', ?, ?, ?)", (name + OWNERSHIP_SUFFIX, person["id"], t, _next_position(pj)))
    util.log("member_added", project=pj.slug, person=person["id"], groups=group_names)


def projects_of(store: Store, person: sqlite3.Row) -> list[dict[str, str]]:
    out = []
    for slug in store.slugs():
        pj = open_project(store, slug)
        if member(pj, person):
            out.append(info(pj))
    return out


# --------------------------------------------------------------------------- invitations

def create_invite(pj: Project, actor: Actor, github_login: Any) -> dict[str, str]:
    _person_only(actor)
    require(pj, actor, "manage_members", "Inviting needs the manage_members permission.")
    if github_login in (None, ""):
        github_login = None
    elif not isinstance(github_login, str) or not util.GITHUB_LOGIN_RE.fullmatch(github_login):
        raise bad_request("invalid_login", "github_login must be a GitHub login.")
    code = f"{pj.slug}.{util.new_secret(24)}"      # the slug says which project's database to look in
    t = util.now()
    with pj.db:
        pj.db.execute("INSERT INTO invites (digest, github_login, created_by, created, expires) VALUES (?, ?, ?, ?, ?)",
                      (util.digest(code), github_login, actor.person_id, t, t + config.get().invite_ttl_s))
    util.log("invite_created", project=pj.slug, by=actor.person_id, for_login=github_login)
    return {"url": f"{config.get().public_url}/join/{code}", "id": util.digest(code)[:INVITE_ID_LEN]}


INVITE_ID_LEN = 16


def list_invites(pj: Project, actor: Actor) -> dict[str, Any]:
    """The invitations not used and not expired, newest first. The link itself is not among them: only its digest is
    kept, so it is shown once, when made. An invitation's id is the start of that digest (it tells nothing of the
    link)."""
    _person_only(actor)
    require(pj, actor, "manage_members", "Seeing the invitations needs the manage_members permission.")
    rows = pj.db.execute("SELECT * FROM invites WHERE used IS NULL AND expires >= ? ORDER BY created DESC",
                         (util.now(),)).fetchall()
    return {"invites": [{"id": r["digest"][:INVITE_ID_LEN], "github_login": r["github_login"],
                         "created": util.iso(r["created"]), "expires": util.iso(r["expires"])} for r in rows]}


def revoke_invite(pj: Project, actor: Actor, invite_id: Any) -> dict[str, Any]:
    """An unused invitation no longer works: it is removed (manage_members)."""
    _person_only(actor)
    require(pj, actor, "manage_members", "Revoking an invitation needs the manage_members permission.")
    if not isinstance(invite_id, str) or not re.fullmatch(f"[0-9a-f]{{{INVITE_ID_LEN}}}", invite_id):
        raise not_found("There is no such invitation.")
    rows = pj.db.execute("SELECT digest FROM invites WHERE substr(digest, 1, ?) = ? AND used IS NULL",
                         (INVITE_ID_LEN, invite_id)).fetchall()
    if len(rows) != 1:
        raise not_found("There is no such invitation.")
    with pj.db:
        pj.db.execute("DELETE FROM invites WHERE digest = ?", (rows[0]["digest"],))
    util.log("invite_revoked", project=pj.slug, by=actor.person_id)
    return {"revoked": invite_id}


def _invite(store: Store, code: str) -> tuple[Project, sqlite3.Row]:
    slug = code.partition(".")[0]
    db = store.project(slug)
    row = db.execute("SELECT * FROM invites WHERE digest = ?", (util.digest(code),)).fetchone() if db else None
    if not row:
        raise not_found("This invitation does not exist. Ask for a new one.")
    return Project(store, slug, db), row


def invite_preview(store: Store, code: str) -> dict[str, Any]:
    """What the invitation page shows before the person accepts."""
    pj, row = _invite(store, code)
    usable = not row["used"] and row["expires"] >= util.now()
    return {"project": info(pj), "usable": usable, "github_login": row["github_login"]}


def accept_invite(store: Store, code: str, person: sqlite3.Row) -> dict[str, str]:
    pj, row = _invite(store, code)
    if row["used"] or row["expires"] < util.now():
        raise gone("This invitation was used or has expired. Ask for a new one.")
    if row["github_login"] and row["github_login"].lower() != person["github_login"].lower():
        raise forbidden("This invitation is for another GitHub account.")
    if not member(pj, person):          # already a member: the invitation is simply spent
        _admit(pj, person, ["human"])
    with pj.db:
        pj.db.execute("UPDATE invites SET used = ?, used_by = ? WHERE digest = ?", (util.now(), person["id"], row["digest"]))
    util.log("invite_used", project=pj.slug, person=person["id"])
    return {"project": pj.slug, "name": person["name"]}


# --------------------------------------------------------------------------- views

def _owners(pj: Project) -> dict[int, str]:
    return {r["person_id"]: r["name"] for r in pj.db.execute("SELECT person_id, name FROM people")}


def avatar(pj: Project, kind: str, member_id: int) -> str | None:
    """The version of a member's avatar (avatars.py), None when it has none. People's views only."""
    r = pj.db.execute("SELECT version FROM avatars WHERE member_kind = ? AND member_id = ?", (kind, member_id)).fetchone()
    return r["version"] if r else None


def status_since(a: sqlite3.Row) -> float | None:
    """Where the agent's update period counts from: its status's last change, or the moment its person asked for
    updates (update_every_h) if that came later. None: neither."""
    times = [x for x in (a["status_at"], a["update_every_at"]) if x is not None]
    return max(times) if times else None


def status_overdue(a: sqlite3.Row, t: float | None = None) -> bool:
    """The agent's person asked for a status update every update_every_h hours (ASTERISM_STATUS_HOUR_S each) and
    the last is older than that."""
    if not a["update_every_h"]:
        return False
    since = status_since(a)
    t = util.now() if t is None else t
    return since is not None and t - since >= a["update_every_h"] * config.get().status_hour_s


def agent_view(pj: Project, a: sqlite3.Row, owners: dict[int, str] | None = None, work: bool = False) -> dict[str, Any]:
    """An agent as the member lists give it. `work`: for people, also what it is doing (presence.work: `work`,
    `last_active` as its session's last activity), its status (title, when it changed, overdue) and its avatar; what
    agents read (whoami) stays without them."""
    owners = owners if owners is not None else _owners(pj)
    because = presence.offline_because(pj.slug, a, pj.db)
    view = {"name": a["name"], "owner": owners.get(a["person_id"], ""), "kind": a["kind"], "model": a["model"],
            "groups": [g["name"] for g in groups_of(pj, "agent", a["id"])],
            "online": because is None, "offline_because": because,
            "last_active": util.iso(a["last_active"]), "generation": a["generation"]}
    if work:
        view.update(presence.work(pj.slug, a, pj.db, because is None))
        view["status"] = {"title": a["status_title"], "at": util.iso(a["status_at"]), "overdue": status_overdue(a)}
        view["avatar"] = avatar(pj, "agent", a["id"])
    return view


def person_online(row: sqlite3.Row) -> bool:
    """A person is online while a page of the project is open: its last beat is recent enough."""
    return row["last_beat"] is not None and util.now() - row["last_beat"] < config.get().person_offline_after_s


def beat(pj: Project, actor: Actor) -> dict[str, Any]:
    """An open page of the project says it is still open. Nothing is announced or logged."""
    _person_only(actor)
    with pj.db:
        pj.db.execute("UPDATE people SET last_beat = ? WHERE person_id = ?", (util.now(), actor.person_id))
    return {"online": True}


def people_and_agents(pj: Project, work: bool = False) -> dict[str, Any]:
    """Every member. `work`: for people (agent_view), also what agents are doing and everyone's avatar."""
    owners = _owners(pj)
    people = []
    for r in pj.db.execute("SELECT * FROM people ORDER BY joined, person_id"):
        acc = accounts.person(pj.accounts, r["person_id"])
        view = {"name": r["name"], "github_login": acc["github_login"] if acc else "",
                "groups": [g["name"] for g in groups_of(pj, "person", r["person_id"])], "online": person_online(r)}
        if work:
            view["status"] = {"title": r["status_title"]}
            view["avatar"] = avatar(pj, "person", r["person_id"])
        people.append(view)
    agents = [agent_view(pj, a, owners, work) for a in pj.db.execute("SELECT * FROM agents ORDER BY id")]
    return {"people": people, "agents": agents}


def ordered_groups(pj: Project) -> list[sqlite3.Row]:
    """Every group: the non-default ones in their order (the highest first), then the default ones."""
    return pj.db.execute("SELECT * FROM groups ORDER BY kind = 'default', position, id").fetchall()


def group_list(pj: Project) -> list[dict[str, Any]]:
    """The groups in their order; a non-default group with its position (0 is the highest) and whether it is shown
    separately; the default groups last, marked default."""
    owners = _owners(pj)
    out = []
    position = 0
    for g in ordered_groups(pj):
        item: dict[str, Any] = {"name": g["name"], "kind": g["kind"], "permissions": _stored(g)}
        if g["kind"] == "default":
            item["default"] = True
        else:
            item["position"] = position
            item["separate"] = bool(g["separate"])
            position += 1
        if g["kind"] == "ownership":
            item["owner"] = owners.get(g["owner_person"], "")
            # What others may do with that person's agents: its permissions, also by name.
            item["switches"] = {k: k in item["permissions"] for k in SWITCHES}
        out.append(item)
    return out


def members_view(pj: Project, actor: Actor) -> dict[str, Any]:
    """Everyone with their groups, the groups, and who is asking with what they hold (the page offers only what
    the requester may do)."""
    require(pj, actor, "read", "Reading the project needs the read permission.")
    mine = permissions(pj, actor)
    return {"project": info(pj), **people_and_agents(pj, work=True), "groups": group_list(pj),
            "me": {"name": person_name(pj, actor.person_id), "permissions": [p for p in PERMISSIONS if p in mine]}}


def switches(pj: Project, person_id: int) -> dict[str, bool]:
    """What others may do with the person's agents: the permissions of the person's own agent group."""
    g = ownership_group(pj, person_id)
    have = set(json.loads(g["permissions"])) if g else set()
    return {k: k in have for k in SWITCHES}


def switch_on(pj: Project, person_id: int, which: str) -> bool:
    return switches(pj, person_id)[which]


def set_switches(pj: Project, actor: Actor, values: Any) -> dict[str, Any]:
    """Only the person themselves sets what others may do with their agents (the permissions of their own group)."""
    _person_only(actor)
    if not isinstance(values, dict) or not set(values) <= set(SWITCHES) \
            or not all(isinstance(v, bool) for v in values.values()):
        raise bad_request("invalid_switches", "Send any of " + ", ".join(SWITCHES) + " as true or false.")
    _set_switches(pj, actor, values, ownership_group(pj, actor.person_id))
    return {"switches": switches(pj, actor.person_id)}


def _set_switches(pj: Project, actor: Actor, values: dict[str, bool], g: sqlite3.Row) -> dict[str, Any]:
    if values:
        now = {**switches(pj, actor.person_id), **values}
        perms = [p for p in json.loads(g["permissions"]) if p not in SWITCHES] + [k for k in SWITCHES if now[k]]
        with pj.db:
            pj.db.execute("UPDATE groups SET permissions = ? WHERE id = ?", (json.dumps(perms), g["id"]))
        util.log("switches_set", project=pj.slug, person=actor.person_id, switches=values)


def credential_view(c: sqlite3.Row) -> dict[str, Any]:
    return {"id": c["id"], "kind": c["kind"], "label": c["label"], "via": c["via"], "created": util.iso(c["created"]),
            "last_used": util.iso(c["last_used"])}


def my_view(pj: Project, actor: Actor) -> dict[str, Any]:
    owners = _owners(pj)
    # Each agent with the credential its session is bound through (null when none): only its own person sees it.
    agents = [{**agent_view(pj, a, owners, work=True), "credential": a["credential_id"]} for a in
              pj.db.execute("SELECT * FROM agents WHERE person_id = ? ORDER BY id", (actor.person_id,))]
    creds = []
    me = pj.accounts.execute("SELECT writer FROM people WHERE id = ?", (actor.person_id,)).fetchone()
    for c in pj.db.execute("SELECT * FROM credentials WHERE person_id = ? AND revoked IS NULL ORDER BY id",
                           (actor.person_id,)):
        view = credential_view(c)
        if c["kind"] == "computer":     # whether that computer's program holds its connection now
            view["connected"] = presence.computer_connected(pj.slug, c["id"], pj.db)
            view["last_seen"] = util.iso(c["last_poll"])
            # The computer that writes this person's changes to the repositories' files (w3: the machine the account
            # chose), whether its program said it has git (null: not said, a program before 0.1.12), which computer
            # it is across projects and the program's version (null: not said, a program before 0.1.13).
            view["machine"], view["version"] = c["machine"], c["version"]
            view["writer"] = bool(me and c["machine"] is not None and me["writer"] == c["machine"])
            view["git"] = None if c["git"] is None else bool(c["git"])
            # The sessions its program can wake that no agent is bound to (not registered as agents yet).
            view["sessions_unbound"] = pj.db.execute(
                "SELECT count(*) FROM computer_sessions s WHERE s.credential_id = ? AND NOT EXISTS (SELECT 1 FROM "
                "agents a WHERE a.credential_id = s.credential_id AND a.session = s.session)", (c["id"],)).fetchone()[0]
            if c["quotas"] is not None:  # what its program last reported (1x); only its own person sees it
                view["quotas"] = [dict(q, at=util.iso(c["quotas_at"])) for q in json.loads(c["quotas"])]
        creds.append(view)
    return {"agents": agents, "credentials": creds, "switches": switches(pj, actor.person_id),
            "program": downloads.program(config.get().data)}


# --------------------------------------------------------------------------- credentials

def issue_credential(pj: Project, person_id: int, kind: str, label: str, via: str) -> tuple[int, str]:
    """A new credential for a computer or a connector; `via` says how it came (invite, device, connector).
    Returns (id, the secret); only its digest is kept."""
    secret = "ast_" + util.new_secret()
    with pj.db:
        cid = pj.db.execute("INSERT INTO credentials (digest, person_id, kind, label, created, via) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (util.digest(secret), person_id, kind, label, util.now(), via)).lastrowid
    util.log("credential_issued", project=pj.slug, person=person_id, credential=cid, kind=kind)
    return cid, secret


def revoke_credential(pj: Project, actor: Actor, cred_id: int) -> dict[str, Any]:
    _person_only(actor)
    c = pj.db.execute("SELECT * FROM credentials WHERE id = ? AND person_id = ? AND revoked IS NULL",
                      (cred_id, actor.person_id)).fetchone()
    if not c:
        raise not_found("You have no such credential.")
    _revoke(pj, "id = ?", (cred_id,))
    util.log("credential_revoked", project=pj.slug, credential=cred_id, by=actor.person_id)
    return {"revoked": cred_id}


def _revoke(pj: Project, where: str, args: tuple[Any, ...]) -> None:
    """Revoke credentials and unbind the sessions that came through them, so their agents go offline."""
    rows = pj.db.execute(f"SELECT id, person_id FROM credentials WHERE revoked IS NULL AND {where}", args).fetchall()
    ids, people = [r["id"] for r in rows], {r["person_id"] for r in rows}
    if not ids:
        return
    marks = ",".join("?" * len(ids))
    bound = [r["id"] for r in pj.db.execute(f"SELECT id FROM agents WHERE credential_id IN ({marks})", ids)]
    with pj.db:
        pj.db.execute(f"UPDATE credentials SET revoked = ? WHERE id IN ({marks})", (util.now(), *ids))
        pj.db.execute(f"UPDATE agents SET session = NULL, credential_id = NULL, last_poll = NULL "
                      f"WHERE credential_id IN ({marks})", ids)
    with pj.accounts:
        pj.accounts.execute(f"DELETE FROM oauth_tokens WHERE slug = ? AND credential_id IN ({marks})", (pj.slug, *ids))
    # A computer revoked in its last project writes nobody's files any more: its person is back on the server path.
    from . import writer                # writer imports this module
    for pid in people:
        writer.settle(pj.store, pid)
    for aid in bound:
        presence.binding_changed(pj.slug, aid)
    for cid in ids:                     # an open computer poll with a revoked credential ends with 401
        presence.computer_changed(pj.slug, cid)


# --------------------------------------------------------------------------- removing members

def remove_member(pj: Project, actor: Actor, name: str) -> dict[str, Any]:
    """Remove an agent (its person, or manage_members) or a person with everything that was theirs."""
    _person_only(actor)
    agent = pj.db.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
    if agent:
        if agent["person_id"] != actor.person_id:
            require(pj, actor, "manage_members", "Removing another person's agent needs the manage_members permission.")
        _purge_agents(pj, "id = ?", (agent["id"],))
        util.log("agent_removed", project=pj.slug, agent=name, by=actor.person_id)
        return {"removed": name}
    person = pj.db.execute("SELECT * FROM people WHERE name = ?", (name,)).fetchone()
    if not person:
        raise not_found(f"There is no member '{name}'.")
    pid = person["person_id"]
    if pid != actor.person_id:
        require(pj, actor, "manage_members", "Removing people needs the manage_members permission.")
        if not person_permissions(pj, pid) <= permissions(pj, actor):
            raise forbidden(f"'{name}' holds permissions you do not hold, so you cannot remove them.")
    if "owner" in {g["name"] for g in groups_of(pj, "person", pid)} and _owners_left(pj, pid) == 0:
        raise conflict("The project needs at least one person in 'owner'.")
    _revoke(pj, "person_id = ?", (pid,))
    _purge_agents(pj, "person_id = ?", (pid,))
    own = ownership_group(pj, pid)
    with pj.db:
        pj.db.execute("DELETE FROM group_members WHERE member_kind = 'person' AND member_id = ?", (pid,))
        if own:
            pj.db.execute("DELETE FROM group_members WHERE group_id = ?", (own["id"],))
            pj.db.execute("DELETE FROM channel_overrides WHERE group_id = ?", (own["id"],))
            pj.db.execute("DELETE FROM groups WHERE id = ?", (own["id"],))
        pj.db.execute("DELETE FROM superseded WHERE person_id = ?", (pid,))
        pj.db.execute("DELETE FROM schedules WHERE person_id = ?", (pid,))     # a person's schedules go with them
        _forget_reader(pj, "person", pid)
        pj.db.execute("DELETE FROM people WHERE person_id = ?", (pid,))
    with pj.accounts:
        pj.accounts.execute("DELETE FROM oauth_tokens WHERE slug = ? AND person_id = ?", (pj.slug, pid))
    util.log("person_removed", project=pj.slug, person=pid, by=actor.person_id)
    return {"removed": name}


def _forget_reader(pj: Project, kind: str, member_id: int) -> None:
    """A removed member's per-reader records and its avatar (inside the caller's transaction). Its messages stay."""
    for table in ("levels", "reads"):
        pj.db.execute(f"DELETE FROM {table} WHERE reader_kind = ? AND reader_id = ?", (kind, member_id))
    pj.db.execute("DELETE FROM mutes WHERE member_kind = ? AND member_id = ?", (kind, member_id))
    pj.db.execute("DELETE FROM avatars WHERE member_kind = ? AND member_id = ?", (kind, member_id))


def _purge_agents(pj: Project, where: str, args: tuple[Any, ...]) -> None:
    ids = [r["id"] for r in pj.db.execute(f"SELECT id FROM agents WHERE {where}", args)]
    with pj.db:
        for aid in ids:
            pj.db.execute("DELETE FROM group_members WHERE member_kind = 'agent' AND member_id = ?", (aid,))
            pj.db.execute("DELETE FROM superseded WHERE agent_id = ?", (aid,))
            _forget_reader(pj, "agent", aid)
            pj.db.execute("DELETE FROM deliveries WHERE agent_id = ?", (aid,))
            pj.db.execute("DELETE FROM chain_reminders WHERE agent_id = ?", (aid,))
            pj.db.execute("DELETE FROM followups WHERE agent_id = ?", (aid,))
            pj.db.execute("DELETE FROM subscriptions WHERE agent_id = ?", (aid,))
            pj.db.execute("DELETE FROM agent_states WHERE agent_id = ?", (aid,))
            pj.db.execute("DELETE FROM agents WHERE id = ?", (aid,))
    for aid in ids:
        presence.binding_changed(pj.slug, aid)
