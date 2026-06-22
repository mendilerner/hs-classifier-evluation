"""
service_token — get a SERVICE-ACCOUNT token for an external app calling the toolkit.

No browser, no human: a headless process authenticates with its Keycloak client
via the OAuth2 client_credentials grant. The identity the toolkit sees is the
client itself (its client_id), not a person. The token is cached in-process and
refreshed automatically (~every 5 min).

Env:
    CURA_AUTH_ENV=dev|prod
    KEYCLOAK_REALM=entic
    KEYCLOAK_CLIENT_ID=svc-my-app          # a client with "Service accounts roles = ON"
    KEYCLOAK_CLIENT_SECRET=<from Vault>
    KEYCLOAK_VERIFY_SSL=true               # false only in dev
"""

import os
import time
import requests
from pathlib import Path

requests.packages.urllib3.disable_warnings()


def _load_dotenv() -> None:
    """Find the nearest .env by walking UP from this file (typically the project
    root) and load its KEY=VALUE lines into os.environ. A single .env at the repo
    root is enough — no per-folder files. A real env var always wins (setdefault)."""
    start = Path(__file__).resolve().parent
    for folder in [start, *start.parents]:
        env_path = folder / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
            return


_load_dotenv()

_KEYCLOAK_BASE = {
    "dev": "https://authentik.mdev.mehes.gov.il",
    "prod": "https://authentik.prod.mehes.gov.il",
}.get(os.environ.get("CURA_AUTH_ENV", "dev"), "https://authentik.mdev.mehes.gov.il")
_REALM = os.environ.get("KEYCLOAK_REALM", "entic")
TOKEN_ENDPOINT = f"{_KEYCLOAK_BASE}/realms/{_REALM}/protocol/openid-connect/token"
_VERIFY = False

_token = None
_expires_at = 0.0


def get_service_token() -> str:
    """Return a cached client_credentials access token, fetching/refreshing as needed."""
    global _token, _expires_at
    if _token and time.time() < _expires_at - 30:
        return _token
    r = requests.post(
        TOKEN_ENDPOINT,
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["KEYCLOAK_CLIENT_ID"],
            "client_secret": os.environ["KEYCLOAK_CLIENT_SECRET"],
        },
        verify=_VERIFY,
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    _token = data["access_token"]
    _expires_at = time.time() + data.get("expires_in", 300)
    return _token
