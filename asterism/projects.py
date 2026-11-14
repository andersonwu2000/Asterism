"""A project's own data: members, groups and permissions, invitations, credentials.

Every entrance (web JSON API, pages, the agent API, MCP tools) calls these functions; none of them
repeats a rule. A function that needs a permission takes an Actor and checks it here.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable

from . import accounts, config, downloads, presence, util
from .errors import bad_request, conflict, forbidden, gone, not_found
from .store import Store

PERMISSIONS = ["read", "post", "create_channel", "create_schedule", "assign_tasks", "manage_own_agents",
               "edit_tasks", "manage_members", "manage_groups", "project_settings"]
MANAGEMENT = {"manage_members", "manage_groups", "project_settings"}
DEFAULT_GROUPS = [
    ("owner", PERMISSIONS),
    ("human", ["read", "post", "create_channel", "create_schedule", "assign_tasks", "manage_own_agents"]),
    ("ai", ["read", "post", "edit_tasks"]),
]
# The four switches of a person's ownership group. others_assign is not enforced yet (no tasks).
SWITCHES = ("others_mention", "others_channel", "others_assign", "others_regroup")
OWNERSHIP_SUFFIX = "-agents"
NAME_RULE = "A name is 1 to 40 letters, digits, '.', '_' or '-', starting with a letter or digit."


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


def info(pj: Project) -> dict[str, str]:
    r = pj.row()
    return {"name": r["name"], "slug": r["slug"], "repo": r["repo"]}


# --------------------------------------------------------------------------- creating a project (admin)

def create_project(store: Store, slug: str, name: str, repo: str, owner_login: str) -> None:
    if not util.valid_slug(slug):
        raise ValueError("the slug must match [a-z0-9][a-z0-9-]{0,39} and not be a reserved word")
    if not name.strip():
        raise ValueError("the name must not be empty")
    if not util.GITHUB_LOGIN_RE.fullmatch(owner_login):
        raise ValueError("the owner must be a GitHub login")
    if not repo.startswith(("https://", "http://")):
        raise ValueError("the repo must be an address (https://...)")
    if store.project(slug) is not None:
        raise ValueError(f"the project '{slug}' exists already")
    conn, tmp = store.new_project_db(slug)
    t = util.now()
    conn.execute("INSERT INTO project (id, slug, name, repo, owner_login, created) VALUES (1, ?, ?, ?, ?, ?)",
                 (slug, name.strip(), repo, owner_login, t))
    for gname, perms in DEFAULT_GROUPS:
        conn.execute("INSERT INTO groups (name, kind, permissions, created) VALUES (?, 'default', ?, ?)",
                     (gname, json.dumps(perms), t))
    store.publish_project_db(conn, tmp, slug)


# --------------------------------------------------------------------------- names

def check_name(name: Any) -> str:
    if not util.valid_name(name):
        raise bad_request("invalid_name", NAME_RULE)
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


def _perms(rows: Iterable[sqlite3.Row]) -> set[str]:
    out: set[str] = set()
    for g in rows:
        out.update(json.loads(g["permissions"]))
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
    check_name(name)
    if name.lower().endswith(OWNERSHIP_SUFFIX):
        raise conflict(f"Names ending in '{OWNERSHIP_SUFFIX}' are kept for each person's own group. Choose another name.")
    if not isinstance(perms, list) or not all(isinstance(p, str) and p in PERMISSIONS for p in perms):
        raise bad_request("invalid_permissions", "permissions must be a list drawn from: " + ", ".join(PERMISSIONS))
    if not set(perms) <= permissions(pj, actor):
        raise forbidden("A group can only carry permissions you hold yourself.")
    holder = name_holder(pj, name)
    if holder:
        raise conflict(describe_holder(pj, holder) + ". Choose another name.")
    perms = [p for p in PERMISSIONS if p in perms]
    with pj.db:
        pj.db.execute("INSERT INTO groups (name, kind, permissions, created) VALUES (?, 'custom', ?, ?)",
                      (name, json.dumps(perms), util.now()))
    util.log("group_created", project=pj.slug, group=name, by=actor.person_id)
    return {"name": name, "kind": "custom", "permissions": perms}


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
            if not ownership_group(pj, agent["person_id"])["others_regroup"]:
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


def groups_assignable(pj: Project, actor: Actor) -> list[str]:
    """The groups a person may give their own agents: the non-ownership groups they are in."""
    return [g["name"] for g in groups_of(pj, "person", actor.person_id) if g["kind"] != "ownership"]


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
        pj.db.execute("INSERT INTO groups (name, kind, permissions, owner_person, created) "
                      "VALUES (?, 'ownership', '[]', ?, ?)", (name + OWNERSHIP_SUFFIX, person["id"], t))
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
    return {"url": f"{config.get().public_url}/join/{code}"}


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


def agent_view(pj: Project, a: sqlite3.Row, owners: dict[int, str] | None = None) -> dict[str, Any]:
    owners = owners if owners is not None else _owners(pj)
    because = presence.offline_because(pj.slug, a, pj.db)
    return {"name": a["name"], "owner": owners.get(a["person_id"], ""), "kind": a["kind"],
            "groups": [g["name"] for g in groups_of(pj, "agent", a["id"])],
            "online": because is None, "offline_because": because, "last_active": util.iso(a["last_active"]),
            "generation": a["generation"]}


def people_and_agents(pj: Project) -> dict[str, Any]:
    owners = _owners(pj)
    people = []
    for r in pj.db.execute("SELECT * FROM people ORDER BY joined, person_id"):
        acc = accounts.person(pj.accounts, r["person_id"])
        # A person's presence comes with the live web connection of a later slice; until then nobody is shown online.
        people.append({"name": r["name"], "github_login": acc["github_login"] if acc else "",
                       "groups": [g["name"] for g in groups_of(pj, "person", r["person_id"])], "online": False})
    agents = [agent_view(pj, a, owners) for a in pj.db.execute("SELECT * FROM agents ORDER BY id")]
    return {"people": people, "agents": agents}


def group_list(pj: Project) -> list[dict[str, Any]]:
    owners = _owners(pj)
    out = []
    for g in pj.db.execute("SELECT * FROM groups ORDER BY id"):
        item: dict[str, Any] = {"name": g["name"], "kind": g["kind"], "permissions": json.loads(g["permissions"])}
        if g["kind"] == "ownership":
            item["owner"] = owners.get(g["owner_person"], "")
        out.append(item)
    return out


def members_view(pj: Project, actor: Actor) -> dict[str, Any]:
    require(pj, actor, "read", "Reading the project needs the read permission.")
    return {"project": info(pj), **people_and_agents(pj), "groups": group_list(pj)}


def switches(pj: Project, person_id: int) -> dict[str, bool]:
    g = ownership_group(pj, person_id)
    return {k: bool(g[k]) for k in SWITCHES}


def set_switches(pj: Project, actor: Actor, values: Any) -> dict[str, Any]:
    """Only the person themselves sets the switches of their own group."""
    _person_only(actor)
    if not isinstance(values, dict) or not set(values) <= set(SWITCHES) \
            or not all(isinstance(v, bool) for v in values.values()):
        raise bad_request("invalid_switches", "Send any of " + ", ".join(SWITCHES) + " as true or false.")
    if values:
        cols = ", ".join(f"{k} = ?" for k in values)       # keys were checked against SWITCHES above
        with pj.db:
            pj.db.execute(f"UPDATE groups SET {cols} WHERE kind = 'ownership' AND owner_person = ?",
                          (*[int(v) for v in values.values()], actor.person_id))
        util.log("switches_set", project=pj.slug, person=actor.person_id, switches=values)
    return {"switches": switches(pj, actor.person_id)}


def credential_view(c: sqlite3.Row) -> dict[str, Any]:
    return {"id": c["id"], "kind": c["kind"], "label": c["label"], "via": c["via"], "created": util.iso(c["created"]),
            "last_used": util.iso(c["last_used"])}


def my_view(pj: Project, actor: Actor) -> dict[str, Any]:
    owners = _owners(pj)
    agents = [agent_view(pj, a, owners) for a in
              pj.db.execute("SELECT * FROM agents WHERE person_id = ? ORDER BY id", (actor.person_id,))]
    creds = []
    for c in pj.db.execute("SELECT * FROM credentials WHERE person_id = ? AND revoked IS NULL ORDER BY id",
                           (actor.person_id,)):
        view = credential_view(c)
        if c["kind"] == "computer":     # whether that computer's program holds its connection now
            view["connected"] = presence.computer_connected(pj.slug, c["id"], pj.db)
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
    ids = [r["id"] for r in pj.db.execute(f"SELECT id FROM credentials WHERE revoked IS NULL AND {where}", args)]
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
            pj.db.execute("DELETE FROM groups WHERE id = ?", (own["id"],))
        pj.db.execute("DELETE FROM superseded WHERE person_id = ?", (pid,))
        _forget_reader(pj, "person", pid)
        pj.db.execute("DELETE FROM people WHERE person_id = ?", (pid,))
    with pj.accounts:
        pj.accounts.execute("DELETE FROM oauth_tokens WHERE slug = ? AND person_id = ?", (pj.slug, pid))
    util.log("person_removed", project=pj.slug, person=pid, by=actor.person_id)
    return {"removed": name}


def _forget_reader(pj: Project, kind: str, member_id: int) -> None:
    """A removed member's per-reader records (inside the caller's transaction). Its messages stay."""
    for table in ("levels", "reads"):
        pj.db.execute(f"DELETE FROM {table} WHERE reader_kind = ? AND reader_id = ?", (kind, member_id))
    pj.db.execute("DELETE FROM mutes WHERE member_kind = ? AND member_id = ?", (kind, member_id))


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
            pj.db.execute("DELETE FROM agents WHERE id = ?", (aid,))
    for aid in ids:
        presence.binding_changed(pj.slug, aid)
