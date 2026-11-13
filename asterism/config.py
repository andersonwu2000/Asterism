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
    device_ttl_s: float             # a device authorisation request nobody approved expires
    access_ttl_s: float             # OAuth access token lifetime
    invite_ttl_s: float
    recent_speaker_s: float         # an agent that spoke in a channel this recently still hears it
    redeliver_after_s: float        # a delivery nobody acknowledged is handed out again after this long
    remind_after_s: float           # an important message not answered for this long is followed by a reminder
    subscription_ttl_s: float       # longest lifetime of an event subscription
    github_web_url: str            # no trailing slash; sign-in page and code exchange
    github_api_url: str             # no trailing slash; "who is this"

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
                    device_ttl_s=_env_s("ASTERISM_DEVICE_TTL_S", 600),
                    access_ttl_s=_env_s("ASTERISM_ACCESS_TTL_S", 3600),
                    invite_ttl_s=_env_s("ASTERISM_INVITE_TTL_S", 604800),
                    recent_speaker_s=_env_s("ASTERISM_RECENT_SPEAKER_S", 1800),
                    redeliver_after_s=_env_s("ASTERISM_REDELIVER_AFTER_S", 30),
                    remind_after_s=_env_s("ASTERISM_REMIND_AFTER_S", 300),
                    subscription_ttl_s=_env_s("ASTERISM_SUBSCRIPTION_TTL_S", 86400),
                    github_web_url=_env_url("ASTERISM_GITHUB_WEB_URL", "https://github.com"),
                    github_api_url=_env_url("ASTERISM_GITHUB_API_URL", "https://api.github.com"))


def use(s: Settings) -> Settings:
    global _current
    _current = s
    return s


def get() -> Settings:
    if _current is None:
        raise RuntimeError("settings are not loaded")
    return _current
