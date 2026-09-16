# local-dev — call the toolkit as YOURSELF

For a person running a script locally. You authenticate as your own AD user via a
one-shot browser login (transparent on a domain-joined machine — no password).
The token is cached in `~/.cura/token.json` and refreshed automatically, so the
browser opens only once.

Everything is in a **single file**: [`example_agent_request.py`](example_agent_request.py)
handles the login (+ cache + refresh) and sends the request. The config lives in
a local `.env`.

## Run
1. `pip install requests cura-auth`
   (`cura-auth` drives the Keycloak login. Install from the internal PyPI feed
   `http://xtfs/DefaultCollection/general/_artifacts/feed/pypi_package/PyPI/cura-auth/overview/`
   or `pip install cura-auth` if that feed is your pip index.)
2. Copy the template and fill in your values:
   ```
   cp .env.example .env      # then edit .env
   ```
3. `python example_agent_request.py`

First run: a browser tab opens and (on a domain machine) returns instantly. After
that the cached token is reused — no browser. The toolkit applies *your*
permissions and your name appears in the logs.

## Why a local `.env` (and not the toolkit's)
- `.env` sits **in this folder** and is **gitignored** — nothing is committed.
- The script reads **only this folder's `.env`**, not the toolkit's own `.env`.
- These values identify the **app** (same for every user), not the person — your
  identity comes from the browser login.

## Prerequisites
- A Keycloak client whose **Valid redirect URIs** include `http://localhost:8765/callback`
  (recommended: a dedicated **public** client `chatbot-agents`, Client authentication OFF,
  Standard flow ON, PKCE), with a `domain_username` mapper so the toolkit identifies
  you as `custom-<you>`.
