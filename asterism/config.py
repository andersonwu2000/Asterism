"""Server settings: the data directory, config.json, and tuning taken from the environment."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data: Path
    public_url: str                 # no trailing slash; also the OAuth issuer
    github_client_id: str
    github_client_secret: str
    test_mode: bool
    offline_after_s: float          # no presence poll for this long = offline
    access_ttl_s: float             # OAuth access token lifetime
    invite_ttl_s: float
    agent_invite_ttl_s: float       # life of an agent invitation link
    notice_grace_s: float           # a session away from its computer's list this long is announced offline
    redeliver_after_s: float        # a delivery nobody acknowledged is handed out again after this long
    remind_after_s: float           # an important message not answered for this long is followed by a reminder
    subscription_ttl_s: float       # longest lifetime of an event subscription
    schedule_min_every_s: float     # the shortest interval of a repeating schedule
    github_web_url: str            # no trailing slash; sign-in page and code exchange
    github_api_url: str             # no trailing slash; "who is this", and the project's repository
    github_app_id: str              # the GitHub app that reads private repositories; "" = none
    github_app_key: str             # path of the app's private key (PEM); "" = DATA/github_app.pem when it exists
    files_refresh_s: float          # the head of a repository's default branch is trusted this long
    files_cache_mb: float           # DATA/cache/ never holds more than this after an answer
    files_max_mb: float             # a larger file of the repository is not fetched
    token_key_file: str             # the key that encrypts people's GitHub tokens; "" = DATA/token.key
    replay_keep_s: float            # the answer to a request with an Idempotency-Key is kept this long
    person_beat_s: float            # an open page of a project tells the server every this long that it is open
    person_offline_after_s: float   # a person whose last page beat is older than this is offline
    status_hour_s: float            # one hour of an agent's update_every_h (shorter in tests)
    active_s: float                 # an agent whose session did something this recently is working (1x)
    write_wait_s: float             # a write handed to the person's chosen computer is waited for this long (w2)
    mcp_trace: bool                 # ASTERISM_MCP_TRACE=1: the connector's log lines also carry values (1q; off)

    @property
    def secure_cookies(self) -> bool:
        return self.public_url.startswith("https://")


_current: Settings | None = None


def _env_s(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _env_url(name: str, default: str) -> str:
    return (os.environ.get(name) or default).rstrip("/")


def load(data: Path, port: int | None = None, test_mode: bool = False) -> Settings:
    """Read DIR/config.json. Real mode refuses to start without what GitHub sign-in needs."""
    data = data.resolve()
    path = data / "config.json"
    conf = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    public = str(conf.get("public_url") or "").rstrip("/")
    if not public and test_mode and port:
        public = f"http://127.0.0.1:{port}"
    cid, secret = str(conf.get("github_client_id") or ""), str(conf.get("github_client_secret") or "")
    if not test_mode:
        missing = [k for k, v in (("public_url", public), ("github_client_id", cid),
                                  ("github_client_secret", secret)) if not v]
        if missing:
            raise SystemExit(f"{path} must set {', '.join(missing)} (or start with --test-mode)")
    return Settings(data=data, public_url=public, github_client_id=cid, github_client_secret=secret,
                    test_mode=test_mode,
                    offline_after_s=_env_s("ASTERISM_OFFLINE_AFTER_S", 120),
                    access_ttl_s=_env_s("ASTERISM_ACCESS_TTL_S", 3600),
                    invite_ttl_s=_env_s("ASTERISM_INVITE_TTL_S", 604800),
                    agent_invite_ttl_s=_env_s("ASTERISM_AGENT_INVITE_TTL_S", 900),
                    notice_grace_s=_env_s("ASTERISM_NOTICE_GRACE_S", 30),
                    redeliver_after_s=_env_s("ASTERISM_REDELIVER_AFTER_S", 30),
                    remind_after_s=_env_s("ASTERISM_REMIND_AFTER_S", 300),
                    subscription_ttl_s=_env_s("ASTERISM_SUBSCRIPTION_TTL_S", 86400),
                    schedule_min_every_s=_env_s("ASTERISM_SCHEDULE_MIN_EVERY_S", 300),
                    github_web_url=_env_url("ASTERISM_GITHUB_WEB_URL", "https://github.com"),
                    github_api_url=_env_url("ASTERISM_GITHUB_API_URL", "https://api.github.com"),
                    github_app_id=(os.environ.get("ASTERISM_GITHUB_APP_ID") or str(conf.get("github_app_id") or "")).strip(),
                    github_app_key=os.environ.get("ASTERISM_GITHUB_APP_KEY") or str(conf.get("github_app_key") or ""),
                    files_refresh_s=_env_s("ASTERISM_FILES_REFRESH_S", 30),
                    files_cache_mb=_env_s("ASTERISM_FILES_CACHE_MB", 200),
                    files_max_mb=_env_s("ASTERISM_FILES_MAX_MB", 25),
                    token_key_file=os.environ.get("ASTERISM_TOKEN_KEY_FILE") or "",
                    replay_keep_s=_env_s("ASTERISM_REPLAY_KEEP_S", 86400),
                    person_beat_s=_env_s("ASTERISM_PERSON_BEAT_S", 20),
                    person_offline_after_s=_env_s("ASTERISM_PERSON_OFFLINE_AFTER_S", 60),
                    status_hour_s=_env_s("ASTERISM_STATUS_HOUR_S", 3600),
                    active_s=_env_s("ASTERISM_ACTIVE_S", 120),
                    write_wait_s=_env_s("ASTERISM_WRITE_WAIT_S", 60),
                    mcp_trace=os.environ.get("ASTERISM_MCP_TRACE", "").strip() == "1")


def use(s: Settings) -> Settings:
    global _current
    _current = s
    return s


def get() -> Settings:
    if _current is None:
        raise RuntimeError("settings are not loaded")
    return _current
