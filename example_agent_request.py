"""
local-dev — call the toolkit as YOURSELF (your AD user, via a browser login).

Everything is in THIS one file: a one-shot browser login (authorization_code +
PKCE, driven by the cura-auth package), the token cached in ~/.cura/token.json
and silently refreshed, then the agent request with that token.

>>> pip install requests cura-auth
>>> Setup (once): copy ".env.example" to ".env" (same folder) and fill it in
>>> Run:          python example_agent_request.py

First run opens a browser tab (transparent on a domain-joined machine — no
password). After that the cached token is reused, so no browser. The toolkit
applies YOUR permissions and your name shows up in the logs.

The ".env" file lives NEXT TO this script and is gitignored — nothing is
committed. This script loads ONLY that local .env (this folder); it does NOT
read the toolkit's own .env. These values identify the APP (same for every
user), not the person — your identity comes from the browser login.
"""
import os
import json
import time
import base64
import http.server
import urllib.parse
import webbrowser
from pathlib import Path

import requests

requests.packages.urllib3.disable_warnings()


def _load_local_env() -> None:
    """Load the .env located NEXT TO this script (this folder only — never a
    parent, never the toolkit's .env). A real environment variable wins."""
    try:
        here = Path(__file__).resolve().parent
    except NameError:                       # pasted in a console: no __file__
        here = Path.cwd()
    env_path = here / ".env"
    if not env_path.exists():
        raise SystemExit(
            f"Missing {env_path}\n"
            f"  -> copy '.env.example' to '.env' (same folder) and fill in your values."
        )
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_local_env()

# cura-auth reads CURA_AUTH_ENV / KEYCLOAK_CLIENT_ID / KEYCLOAK_CLIENT_SECRET from
# os.environ, which the local .env just populated.
from cura_auth import CuraAuth  # noqa: E402  (import after .env is loaded)

# Where to send the request: your local toolkit, or the deployed pod.
TOOLKIT_URL = "http://localhost:8000/api/v1/agents/run"
# TOOLKIT_URL = "https://langraph-infrastructure.mdev.mehes.gov.il/api/v1/agents/run"  # <- pod

REDIRECT_PORT = int(os.environ.get("CURA_CLI_REDIRECT_PORT", "8765"))
REDIRECT_URI  = f"http://localhost:{REDIRECT_PORT}/callback"   # must be in the client's Valid redirect URIs
CACHE_FILE    = Path.home() / ".cura" / "token.json"


# ── login: get a USER token (cache → silent refresh → browser login) ──────────
def _decode_exp(token: str) -> int:
    """Read the JWT `exp` (seconds since epoch) without verifying."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return int(json.loads(base64.urlsafe_b64decode(payload)).get("exp", 0))
    except Exception:
        return 0


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(access_token: str, refresh_token: str) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps({"access_token": access_token, "refresh_token": refresh_token}),
        encoding="utf-8",
    )


def _clear_cache() -> None:
    try:
        CACHE_FILE.unlink()
    except FileNotFoundError:
        pass


def _interactive_login(auth: CuraAuth):
    """Open the browser, capture the code on the loopback, exchange for tokens."""
    login = auth.get_login_url(REDIRECT_URI)
    received = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            received["code"] = params.get("code", [None])[0]
            received["state"] = params.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body>"
                b"<script>window.open('','_self');window.close();</script>"
                b"<h3>Connexion reussie.</h3>Vous pouvez fermer cet onglet."
                b"</body></html>"
            )

        def log_message(self, *args):
            pass  # silence the default stderr logging

    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), _Handler)
    print(f"🔐 Opening your browser to sign in ({REDIRECT_URI}) ...")
    webbrowser.open(login["url"])
    server.handle_request()  # blocks until Keycloak redirects back once
    server.server_close()

    code = received.get("code")
    if not code:
        raise RuntimeError("No authorization code received on the callback.")
    if received.get("state") != login["state"]:
        raise RuntimeError("State mismatch — aborting (possible CSRF).")
    return auth.exchange_code(code, REDIRECT_URI, login["code_verifier"])


def get_user_token(force_login: bool = False) -> str:
    """Return a valid USER access token (cache → silent refresh → browser login)."""
    auth = CuraAuth()

    if force_login:
        _clear_cache()
        ts = _interactive_login(auth)
        _save_cache(ts.access_token, ts.refresh_token)
        return ts.access_token

    cache = _load_cache()
    tok = cache.get("access_token")
    if tok and _decode_exp(tok) - 30 > time.time():          # 1) cached token still valid
        return tok
    if cache.get("refresh_token"):                            # 2) try a silent refresh
        try:
            ts = auth.refresh(cache["refresh_token"])
            _save_cache(ts.access_token, ts.refresh_token)
            return ts.access_token
        except Exception:
            pass
    ts = _interactive_login(auth)                            # 3) full browser login
    _save_cache(ts.access_token, ts.refresh_token)
    return ts.access_token


def authed_request(method: str, url: str, **kwargs):
    """HTTP request with the user's Bearer token, auto-recovering once on 401."""
    headers = dict(kwargs.pop("headers", {}) or {})
    headers["Authorization"] = f"Bearer {get_user_token()}"
    resp = requests.request(method, url, headers=headers, **kwargs)
    if resp.status_code == 401:
        headers["Authorization"] = f"Bearer {get_user_token(force_login=True)}"
        resp = requests.request(method, url, headers=headers, **kwargs)
    return resp


# ── request ──────────────────────────────────────────────────────────────────
response = authed_request(
    "POST",
    TOOLKIT_URL,
    json={
        "agent_name": "debugger",
        "input_data": {
            "message": "prinnt(10",
            "model_name": "llama4-maverick-bf8",
        },
        "mode": "background",
    },
    verify=False,
)

print(f"Status: {response.status_code}")
print(response.json())
