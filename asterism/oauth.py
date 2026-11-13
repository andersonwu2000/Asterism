"""The OAuth authorization server for the ChatGPT connector, written by hand.

What ChatGPT's connector needs (verified live against it): protected resource metadata (RFC 9728),
authorization server metadata (RFC 8414) with an issuer that has no path, dynamic registration of public
clients (RFC 7591), the authorization code flow with PKCE S256, `resource` (RFC 8707) and `iss` on the
redirect (RFC 9207), and rotating refresh tokens.

The `resource` names one project's MCP endpoint; the signed-in person who approves must be a member of
it. Each approval becomes one "connector" credential of that person in that project, shown and revocable
beside their computers. Codes and tokens are stored only as digests.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import sqlite3
import urllib.parse
from typing import Any

from . import config, projects, util
from .agents import Caller, touch_credential
from .errors import ApiError
from .store import Store

CODE_TTL_S = 300
REFRESH_TTL_S = 30 * 24 * 3600
CLIENT_UNUSED_TTL_S = 24 * 3600          # a registered client that never got a token is dropped after this
CHALLENGE_RE = re.compile(r"[A-Za-z0-9_-]{43}")      # S256: base64url of a SHA-256 digest, no padding


class OAuthError(Exception):
    """An error answered in OAuth's own shape: {error, error_description}."""

    def __init__(self, status: int, error: str, description: str):
        super().__init__(description)
        self.status, self.error, self.description = status, error, description


def issuer() -> str:
    return config.get().public_url


def resource_url(slug: str) -> str:
    return f"{config.get().public_url}/{slug}/mcp"


def resource_metadata_url(slug: str) -> str:
    return f"{config.get().public_url}/.well-known/oauth-protected-resource/{slug}/mcp"


def protected_resource_doc(slug: str) -> dict[str, Any]:
    return {"resource": resource_url(slug), "authorization_servers": [issuer()],
            "bearer_methods_supported": ["header"]}


def authorization_server_doc() -> dict[str, Any]:
    base = config.get().public_url
    return {"issuer": issuer(), "authorization_endpoint": base + "/oauth/authorize",
            "token_endpoint": base + "/oauth/token", "registration_endpoint": base + "/oauth/register",
            "response_types_supported": ["code"], "response_modes_supported": ["query"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["none"], "code_challenge_methods_supported": ["S256"],
            "authorization_response_iss_parameter_supported": True}


def slug_of_resource(resource: str | None) -> str | None:
    """The project a `resource` parameter names, or None."""
    if not resource:
        return None
    base = config.get().public_url + "/"
    if not resource.startswith(base) or not resource.endswith("/mcp"):
        return None
    slug = resource[len(base):-len("/mcp")]
    return slug if util.valid_slug(slug) else None


# --------------------------------------------------------------------------- registration

def _redirect_ok(u: Any) -> bool:
    if not isinstance(u, str) or not u or len(u) > 500:
        return False
    p = urllib.parse.urlsplit(u)
    loopback = p.scheme == "http" and p.hostname in ("127.0.0.1", "localhost")
    return (p.scheme == "https" or loopback) and bool(p.hostname) and not p.fragment


def register_client(db: sqlite3.Connection, body: Any) -> dict[str, Any]:
    """Dynamic registration. Every client is public: it proves itself with PKCE, not a secret."""
    if not isinstance(body, dict):
        raise OAuthError(400, "invalid_client_metadata", "the body must be a JSON object")
    uris = body.get("redirect_uris")
    if not isinstance(uris, list) or not 1 <= len(uris) <= 10 or not all(_redirect_ok(u) for u in uris):
        raise OAuthError(400, "invalid_redirect_uri", "redirect_uris must list one to ten https addresses")
    cid = "c_" + util.new_secret(18)
    name = util.clean_label(body.get("client_name")) or "Connector"
    t = util.now()
    with db:
        db.execute("DELETE FROM oauth_clients WHERE created < ? AND client_id NOT IN (SELECT client_id FROM oauth_tokens)",
                   (t - CLIENT_UNUSED_TTL_S,))
        db.execute("INSERT INTO oauth_clients (client_id, name, redirect_uris, created) VALUES (?, ?, ?, ?)",
                   (cid, name, json.dumps(uris), t))
    util.log("oauth_client_registered", client=cid, name=name)
    return {"client_id": cid, "client_id_issued_at": int(t), "client_name": name, "redirect_uris": uris,
            "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
            "token_endpoint_auth_method": "none"}


def client(db: sqlite3.Connection, client_id: str | None) -> sqlite3.Row | None:
    if not client_id:
        return None
    return db.execute("SELECT * FROM oauth_clients WHERE client_id = ?", (client_id,)).fetchone()


# --------------------------------------------------------------------------- authorization

class Untrusted(Exception):
    """The request's client or return address cannot be trusted: answer on our own page, never redirect."""


def check_request(db: sqlite3.Connection, p: dict[str, str]) -> tuple[sqlite3.Row, str]:
    """Returns (client, redirect URI) once both are known to be registered together."""
    c = client(db, p.get("client_id"))
    if not c:
        raise Untrusted("unknown_client")
    uris = json.loads(c["redirect_uris"])
    redirect = p.get("redirect_uri") or (uris[0] if len(uris) == 1 else "")
    if redirect not in uris:
        raise Untrusted("unregistered_redirect")
    return c, redirect


def request_problem(p: dict[str, str]) -> tuple[str, str] | None:
    """A problem the client should hear about on its redirect URI."""
    if p.get("response_type") != "code":
        return "unsupported_response_type", "response_type must be code"
    if not p.get("code_challenge") or p.get("code_challenge_method") != "S256":
        return "invalid_request", "PKCE with code_challenge_method S256 is required"
    if not CHALLENGE_RE.fullmatch(p["code_challenge"]):
        return "invalid_request", "code_challenge must be 43 characters of base64url (S256)"
    if not slug_of_resource(p.get("resource")):
        return "invalid_target", "resource must be the MCP address of a project on this server"
    return None


def back_to_client(redirect: str, **params: Any) -> str:
    """The client's redirect URI with the answer; every answer carries the issuer (RFC 9207)."""
    q = urllib.parse.urlencode({**{k: v for k, v in params.items() if v is not None}, "iss": issuer()})
    return redirect + ("&" if "?" in redirect else "?") + q


def approve(store: Store, person_id: int, c: sqlite3.Row, redirect: str, p: dict[str, str]) -> str:
    """Issue a single-use authorization code; returns the redirect address."""
    code = util.new_secret()
    db = store.accounts()
    with db:
        db.execute("DELETE FROM oauth_codes WHERE expires < ?", (util.now(),))
        db.execute("INSERT INTO oauth_codes (digest, client_id, redirect_uri, person_id, slug, challenge, expires) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?)", (util.digest(code), c["client_id"], redirect, person_id,
                                                    slug_of_resource(p.get("resource")), p["code_challenge"],
                                                    util.now() + CODE_TTL_S))
    util.log("oauth_approved", client=c["client_id"], person=person_id, project=slug_of_resource(p.get("resource")))
    return back_to_client(redirect, code=code, state=p.get("state"))


# --------------------------------------------------------------------------- tokens

def _issue(db: sqlite3.Connection, client_id: str, person_id: int, slug: str, credential_id: int) -> dict[str, Any]:
    access, refresh = util.new_secret(), util.new_secret()
    t, ttl = util.now(), config.get().access_ttl_s
    with db:
        db.execute("DELETE FROM oauth_tokens WHERE expires < ?", (t,))
        for kind, secret, life in (("access", access, ttl), ("refresh", refresh, REFRESH_TTL_S)):
            db.execute("INSERT INTO oauth_tokens (digest, kind, client_id, person_id, slug, credential_id, expires) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?)", (util.digest(secret), kind, client_id, person_id, slug,
                                                       credential_id, t + life))
    return {"access_token": access, "token_type": "Bearer", "expires_in": int(ttl), "refresh_token": refresh}


def token(store: Store, f: dict[str, str]) -> dict[str, Any]:
    db = store.accounts()
    c = client(db, f.get("client_id"))
    if not c:
        raise OAuthError(401, "invalid_client", "unknown client_id")
    if "resource" in f and not slug_of_resource(f["resource"]):
        raise OAuthError(400, "invalid_target", "resource is not a project's MCP address on this server")
    grant = f.get("grant_type")
    if grant == "authorization_code":
        key = util.digest(f.get("code", ""))
        with db:      # single use, whatever happens next
            row = db.execute("SELECT * FROM oauth_codes WHERE digest = ?", (key,)).fetchone()
            db.execute("DELETE FROM oauth_codes WHERE digest = ?", (key,))
        if not row or row["expires"] < util.now():
            raise OAuthError(400, "invalid_grant", "unknown, used or expired code")
        if row["client_id"] != c["client_id"] or f.get("redirect_uri", row["redirect_uri"]) != row["redirect_uri"]:
            raise OAuthError(400, "invalid_grant", "client or redirect_uri does not match the code")
        if "resource" in f and slug_of_resource(f["resource"]) != row["slug"]:
            raise OAuthError(400, "invalid_target", "resource does not match the approval")
        verifier = f.get("code_verifier", "")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest()).decode().rstrip("=")
        if not 43 <= len(verifier) <= 128 or not hmac.compare_digest(challenge.encode("ascii"),
                                                                      str(row["challenge"]).encode("utf-8", "surrogatepass")):
            raise OAuthError(400, "invalid_grant", "PKCE verification failed")
        try:
            pj = projects.open_project(store, row["slug"])
        except ApiError:
            raise OAuthError(400, "invalid_grant", "the project no longer exists") from None
        if not pj.db.execute("SELECT 1 FROM people WHERE person_id = ?", (row["person_id"],)).fetchone():
            raise OAuthError(400, "invalid_grant", "the approving person is no longer a member")
        cred_id, _ = projects.issue_credential(pj, row["person_id"], "connector", c["name"], "connector")
        util.log("oauth_token_issued", client=c["client_id"], person=row["person_id"], grant=grant)
        return _issue(db, c["client_id"], row["person_id"], row["slug"], cred_id)
    if grant == "refresh_token":
        key = util.digest(f.get("refresh_token", ""))
        row = db.execute("SELECT * FROM oauth_tokens WHERE digest = ? AND kind = 'refresh'", (key,)).fetchone()
        if not row or row["expires"] < util.now() or row["client_id"] != c["client_id"]:
            raise OAuthError(400, "invalid_grant", "unknown, used, expired or another client's refresh token")
        if "resource" in f and slug_of_resource(f["resource"]) != row["slug"]:
            raise OAuthError(400, "invalid_target", "resource does not match the grant")
        with db:      # rotated: a public client's refresh token is good for one use
            db.execute("DELETE FROM oauth_tokens WHERE digest = ?", (key,))
        pj = store.project(row["slug"])
        alive = pj and pj.execute("SELECT 1 FROM credentials WHERE id = ? AND revoked IS NULL",
                                  (row["credential_id"],)).fetchone()
        if not alive:
            raise OAuthError(400, "invalid_grant", "the connector's approval was revoked; add the connector again")
        util.log("oauth_token_issued", client=c["client_id"], person=row["person_id"], grant=grant)
        return _issue(db, c["client_id"], row["person_id"], row["slug"], row["credential_id"])
    raise OAuthError(400, "unsupported_grant_type", "grant_type must be authorization_code or refresh_token")


def bearer_caller(store: Store, slug: str, authorization: str | None,
                  session: str | None) -> tuple[Caller | None, str]:
    """(The person and connector credential behind an access token for this project's MCP endpoint, "") or
    (None, a fixed word saying why the token is refused)."""
    scheme, _, tok = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not tok.strip():
        return None, "no_token"
    row = store.accounts().execute("SELECT * FROM oauth_tokens WHERE digest = ? AND kind = 'access'",
                                   (util.digest(tok.strip()),)).fetchone()
    if not row:
        return None, "bad_token"
    if row["expires"] < util.now():
        return None, "expired_token"
    if row["slug"] != slug:
        return None, "wrong_project"
    try:
        pj = projects.open_project(store, slug)
    except ApiError:
        return None, "no_project"
    c = pj.db.execute("SELECT * FROM credentials WHERE id = ? AND revoked IS NULL", (row["credential_id"],)).fetchone()
    if not c:
        return None, "revoked"
    if not pj.db.execute("SELECT 1 FROM people WHERE person_id = ?", (c["person_id"],)).fetchone():
        return None, "not_member"
    touch_credential(pj, c["id"])
    # The header value is a ChatGPT conversation id; keep only a digest of it.
    sid = "oai:" + util.digest(session)[:32] if session else None
    return Caller(pj, c["person_id"], c["id"], sid, "chatgpt"), ""
